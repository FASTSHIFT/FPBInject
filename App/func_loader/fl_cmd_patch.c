/*
 * MIT License
 * Copyright (c) 2026 VIFEX
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

/**
 * @file   fl_cmd_patch.c
 * @brief  FPB patch command handlers (patch/tpatch/dpatch/unpatch/enable)
 */

#include "fl_cmd.h"

#ifndef FL_NO_FPB
#include "fpb_inject.h"
#include "fpb_trampoline.h"
#include "fpb_debugmon.h"
#endif

#ifndef FL_NO_FPB

void fl_cmd_print_fpb_info(fl_context_t* ctx) {
    const fpb_state_t* fpb = fpb_get_state();
    fpb_info_t fpb_info;
    uint32_t num_comps = fpb->num_code_comp;
    uint32_t active_count = 0;
    size_t total_used = 0;

    for (uint32_t i = 0; i < num_comps && i < FL_MAX_SLOTS; i++) {
        if (ctx->slots[i].active) {
            active_count++;
            total_used += ctx->slots[i].code_size;
        }
    }

    fl_println("Used: %u", (unsigned)total_used);
    fl_println("Slots: %u/%u", (unsigned)active_count, (unsigned)num_comps);

    if (fpb_get_info(&fpb_info) == FPB_OK) {
        const char* rev_str = (fpb_info.rev == 0) ? "v1" : (fpb_info.rev == 1) ? "v2" : "unknown";
        fl_println("FPB: %s, %u code + %u lit = %u total, %s", rev_str, fpb_info.num_code_comp, fpb_info.num_lit_comp,
                   fpb_info.total_comp, fpb_info.enabled ? "enabled" : "disabled");

        fl_println("FP_REMAP: 0x%08lX, base=0x%08lX, remap %s", (unsigned long)fpb_info.remap_raw,
                   (unsigned long)fpb_info.remap_base, fpb_info.remap_supported ? "supported" : "not supported");

        static const char* replace_mode_str[] = {"remap", "bp_lo", "bp_hi", "bp_both"};
        for (uint32_t i = 0; i < num_comps && i < FL_MAX_SLOTS && i < FPB_MAX_CODE_COMP; i++) {
            fl_slot_state_t* slot = &ctx->slots[i];
            fpb_comp_info_t* comp = &fpb_info.comp[i];
            const char* mode_str = (comp->replace < 4) ? replace_mode_str[comp->replace] : "?";

            if (slot->active) {
                fl_println("Slot[%u]: 0x%08lX -> 0x%08lX, %u bytes (COMP=0x%08lX, %s, %s)", (unsigned)i,
                           (unsigned long)slot->orig_addr, (unsigned long)slot->target_addr, (unsigned)slot->code_size,
                           (unsigned long)comp->comp_raw, mode_str, comp->enabled ? "on" : "off");
            } else {
                fl_println("Slot[%u]: empty (COMP=0x%08lX, %s)", (unsigned)i, (unsigned long)comp->comp_raw,
                           comp->enabled ? "on" : "off");
            }
        }
    } else {
        fl_println("FPB: not available");
    }
}

/**
 * @brief  Verify CRC for patch commands: covers comp(4B) + orig(4B) + target(4B)
 * @return true if CRC matches or no CRC provided (crc < 0)
 */
bool fl_verify_patch_crc(int crc, uint32_t comp, uintptr_t orig, uintptr_t target) {
    if (crc < 0)
        return true;
    uint32_t comp32 = comp;
    uint32_t orig32 = (uint32_t)orig;
    uint32_t target32 = (uint32_t)target;
    uint16_t calc = 0xFFFF;
    calc = fl_crc16_base(calc, &comp32, sizeof(comp32));
    calc = fl_crc16_base(calc, &orig32, sizeof(orig32));
    calc = fl_crc16_base(calc, &target32, sizeof(target32));
    return fl_verify_crc(crc, calc);
}

fl_error_t fl_cmd_patch(fl_context_t* ctx, const cmd_args_t* args) {
    if (args->orig == 0 || args->target == 0) {
        fl_response(false, "Missing --orig/--target");
        return FL_ERR_ARGS;
    }

    if (!fl_verify_patch_crc(args->crc, args->comp, args->orig, args->target))
        return FL_ERR_CRC;

    if ((uint32_t)args->comp >= fpb_get_state()->num_code_comp || (uint32_t)args->comp >= FL_MAX_SLOTS) {
        fl_response(false, "Invalid comp %lu", (unsigned long)args->comp);
        return FL_ERR_RANGE;
    }

    fpb_result_t ret = fpb_set_patch(args->comp, args->orig, args->target);
    if (ret != FPB_OK) {
        fl_response(false, "fpb_set_patch failed: %d", ret);
        return FL_ERR_HW;
    }

    /* Record slot state, transfer last_alloc ownership to slot */
    ctx->slots[args->comp].active = true;
    ctx->slots[args->comp].orig_addr = args->orig;
    ctx->slots[args->comp].target_addr = args->target;
    ctx->slots[args->comp].code_size = ctx->last_alloc_size;
    ctx->slots[args->comp].alloc_addr = ctx->last_alloc;
    ctx->last_alloc = 0; /* Ownership transferred */
    ctx->last_alloc_size = 0;

    fl_response(true, "Patch %lu: 0x%08lX -> 0x%08lX", (unsigned long)args->comp, (unsigned long)args->orig,
                (unsigned long)args->target);
    return FL_OK;
}

fl_error_t fl_cmd_tpatch(fl_context_t* ctx, const cmd_args_t* args) {
    if (args->orig == 0 || args->target == 0) {
        fl_response(false, "Missing --orig/--target");
        return FL_ERR_ARGS;
    }

#ifndef FPB_NO_TRAMPOLINE
    if (!fl_verify_patch_crc(args->crc, args->comp, args->orig, args->target))
        return FL_ERR_CRC;

    if ((uint32_t)args->comp >= FPB_TRAMPOLINE_COUNT || (uint32_t)args->comp >= FL_MAX_SLOTS) {
        fl_response(false, "Invalid comp %lu (max %d)", (unsigned long)args->comp, FPB_TRAMPOLINE_COUNT - 1);
        return FL_ERR_RANGE;
    }

    /* Set trampoline target in RAM */
    fpb_trampoline_set_target(args->comp, args->target);

    /* Get trampoline address in Flash */
    uint32_t tramp_addr = fpb_trampoline_get_address(args->comp);

    /* Use FPB to redirect original function to trampoline */
    fpb_result_t ret = fpb_set_patch(args->comp, args->orig, tramp_addr);
    if (ret != FPB_OK) {
        fpb_trampoline_clear_target(args->comp);
        fl_response(false, "fpb_set_patch failed: %d", ret);
        return FL_ERR_HW;
    }

    /* Record slot state, transfer last_alloc ownership to slot */
    ctx->slots[args->comp].active = true;
    ctx->slots[args->comp].orig_addr = args->orig;
    ctx->slots[args->comp].target_addr = args->target;
    ctx->slots[args->comp].code_size = ctx->last_alloc_size;
    ctx->slots[args->comp].alloc_addr = ctx->last_alloc;
    ctx->last_alloc = 0; /* Ownership transferred */
    ctx->last_alloc_size = 0;

    fl_response(true, "Trampoline %lu: 0x%08lX -> tramp(0x%08lX) -> 0x%08lX", (unsigned long)args->comp,
                (unsigned long)args->orig, (unsigned long)tramp_addr, (unsigned long)args->target);
#else
    (void)ctx;
    fl_response(false, "Trampoline disabled (FPB_NO_TRAMPOLINE)");
#endif
    return FL_OK;
}

fl_error_t fl_cmd_dpatch(fl_context_t* ctx, const cmd_args_t* args) {
    if (args->orig == 0 || args->target == 0) {
        fl_response(false, "Missing --orig/--target");
        return FL_ERR_ARGS;
    }

#ifndef FPB_NO_DEBUGMON
    if (!fl_verify_patch_crc(args->crc, args->comp, args->orig, args->target))
        return FL_ERR_CRC;

    if ((uint32_t)args->comp >= FPB_DEBUGMON_MAX_REDIRECTS || (uint32_t)args->comp >= FL_MAX_SLOTS) {
        fl_response(false, "Invalid comp %lu (max %d)", (unsigned long)args->comp, FPB_DEBUGMON_MAX_REDIRECTS - 1);
        return FL_ERR_RANGE;
    }

    /* Initialize DebugMonitor if not already done */
    if (!fpb_debugmon_is_active()) {
        if (fpb_debugmon_init() != 0) {
            fl_response(false, "DebugMonitor init failed");
            return FL_ERR_HW;
        }
    }

    /* Set redirect via DebugMonitor */
    int ret = fpb_debugmon_set_redirect(args->comp, args->orig, args->target);
    if (ret != 0) {
        fl_response(false, "fpb_debugmon_set_redirect failed: %d", ret);
        return FL_ERR_HW;
    }

    /* Record slot state, transfer last_alloc ownership to slot */
    ctx->slots[args->comp].active = true;
    ctx->slots[args->comp].orig_addr = args->orig;
    ctx->slots[args->comp].target_addr = args->target;
    ctx->slots[args->comp].code_size = ctx->last_alloc_size;
    ctx->slots[args->comp].alloc_addr = ctx->last_alloc;
    ctx->last_alloc = 0; /* Ownership transferred */
    ctx->last_alloc_size = 0;

    fl_response(true, "DebugMon %lu: 0x%08lX -> 0x%08lX", (unsigned long)args->comp, (unsigned long)args->orig,
                (unsigned long)args->target);
#else
    (void)ctx;
    fl_response(false, "DebugMonitor disabled (FPB_NO_DEBUGMON)");
#endif
    return FL_OK;
}

fl_error_t fl_cmd_unpatch(fl_context_t* ctx, const cmd_args_t* args) {
    uint32_t comp = (uint32_t)args->comp;
    bool all = args->all;

    /* Verify CRC if provided: covers comp(4B) */
    {
        uint32_t comp32 = comp;
        if (!fl_verify_crc(args->crc, fl_crc16(&comp32, sizeof(comp32)))) {
            return FL_ERR_CRC;
        }
    }

    uint32_t num_comps = fpb_get_state()->num_code_comp;
    uint32_t start = all ? 0 : comp;
    uint32_t end = all ? num_comps : comp + 1;

    if (!all && (comp >= num_comps || comp >= FL_MAX_SLOTS)) {
        fl_response(false, "Invalid comp %lu", (unsigned long)comp);
        return FL_ERR_RANGE;
    }

    uint32_t cleared = 0;
    for (uint32_t i = start; i < end && i < FL_MAX_SLOTS; i++) {
        if (ctx->slots[i].active || all) {
#ifndef FPB_NO_TRAMPOLINE
            fpb_trampoline_clear_target(i);
#endif
#ifndef FPB_NO_DEBUGMON
            fpb_debugmon_clear_redirect(i);
#endif
            fpb_clear_patch(i);

            /* Free slot's allocated memory if any */
            if (ctx->slots[i].alloc_addr != 0 && ctx->free_cb) {
                ctx->free_cb((void*)ctx->slots[i].alloc_addr);
            }

            /* Clear slot state */
            ctx->slots[i].active = false;
            ctx->slots[i].orig_addr = 0;
            ctx->slots[i].target_addr = 0;
            ctx->slots[i].code_size = 0;
            ctx->slots[i].alloc_addr = 0;
            cleared++;
        }
    }

    if (all) {
        fl_response(true, "Cleared all %u slots, memory freed", (unsigned)cleared);
    } else {
        fl_response(true, "Cleared slot %lu", (unsigned long)comp);
    }
    return FL_OK;
}

fl_error_t fl_cmd_enable(fl_context_t* ctx, const cmd_args_t* args) {
    if (args->enable < 0) {
        fl_response(false, "Missing --enable (0 or 1)");
        return FL_ERR_ARGS;
    }

    /* Verify CRC if provided: covers comp(4B) + enable(4B) */
    {
        uint32_t comp32 = (uint32_t)args->comp;
        uint32_t enable32 = (uint32_t)args->enable;
        uint16_t calc = 0xFFFF;
        calc = fl_crc16_base(calc, &comp32, sizeof(comp32));
        calc = fl_crc16_base(calc, &enable32, sizeof(enable32));
        if (!fl_verify_crc(args->crc, calc)) {
            return FL_ERR_CRC;
        }
    }

    (void)ctx;
    bool en = args->enable != 0;
    bool all = args->all;
    uint32_t comp = (uint32_t)args->comp;
    uint32_t num_comps = fpb_get_state()->num_code_comp;
    uint32_t start = all ? 0 : comp;
    uint32_t end = all ? num_comps : comp + 1;

    if (!all && (comp >= num_comps || comp >= FL_MAX_SLOTS)) {
        fl_response(false, "Invalid comp %lu", (unsigned long)comp);
        return FL_ERR_RANGE;
    }

    uint32_t changed = 0;
    for (uint32_t i = start; i < end && i < FL_MAX_SLOTS; i++) {
        fpb_result_t ret = fpb_enable_patch(i, en);
        if (ret == FPB_OK) {
            changed++;
        }
    }

    if (all) {
        fl_response(true, "%s %u patches", en ? "Enabled" : "Disabled", (unsigned)changed);
    } else {
        fl_response(true, "%s patch %lu", en ? "Enabled" : "Disabled", (unsigned long)comp);
    }
    return FL_OK;
}

#else /* FL_NO_FPB */

#define FL_NO_FPB_CMD(name)                                      \
    fl_error_t name(fl_context_t* ctx, const cmd_args_t* args) { \
        (void)ctx;                                               \
        (void)args;                                              \
        fl_response(false, "FPB disabled (FL_NO_FPB)");          \
        return FL_ERR_DISABLED;                                  \
    }

FL_NO_FPB_CMD(fl_cmd_patch)
FL_NO_FPB_CMD(fl_cmd_tpatch)
FL_NO_FPB_CMD(fl_cmd_dpatch)
FL_NO_FPB_CMD(fl_cmd_unpatch)
FL_NO_FPB_CMD(fl_cmd_enable)

void fl_cmd_print_fpb_info(fl_context_t* ctx) {
    (void)ctx;
    fl_println("FPB: disabled (FL_NO_FPB)");
}

#undef FL_NO_FPB_CMD

#endif /* FL_NO_FPB */
