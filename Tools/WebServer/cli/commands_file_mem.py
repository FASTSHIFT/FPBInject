"""File and memory command handlers for the FPB CLI.

Extracted from cli.fpb_cli to keep that module under the file-size
limit. These methods are mixed into :class:`FPBCLI` and rely on its
attributes (``_proxy``, ``_fpb``, ``_device_state``) and helpers
(``output_json``, ``output_error``, ``_require_device``,
``_transfer_notice``, ``_make_progress_printer``,
``_cancel_proxy_transfer``, ``_write_local``, ``_looks_like_serial_loss``).
"""

import os

from fpbinject.cli.errors import FPBCLIError


class FileMemCommandsMixin:
    """Device file-system and raw-memory command handlers."""

    def file_list(self, path: str = "/") -> None:
        """List directory contents on device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.file_list(path))
                return

            self._require_device()
            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
            )
            success, entries = ft.flist(path)
            if not success:
                raise FPBCLIError(f"Failed to list directory: {path}")
            self.output_json({"success": True, "path": path, "entries": entries})
        except Exception as e:
            self.output_error(f"file_list failed: {str(e)}", e)

    def file_stat(self, path: str) -> None:
        """Get file/directory stat on device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.file_stat(path))
                return

            self._require_device()
            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
            )
            success, stat = ft.fstat(path)
            if not success:
                raise FPBCLIError(f"Failed to stat: {stat.get('error', 'unknown')}")
            self.output_json({"success": True, "path": path, "stat": stat})
        except Exception as e:
            self.output_error(f"file_stat failed: {str(e)}", e)

    def file_download(self, remote_path: str, local_path: str) -> None:
        """Download a file from device to local path"""
        try:
            if self._proxy:
                self._transfer_notice("downloading", remote_path, 0)
                try:
                    result = self._proxy.file_download(
                        remote_path,
                        progress_cb=self._make_progress_printer(),
                    )
                except KeyboardInterrupt:
                    # Client is going away mid-transfer: tell the server to
                    # cancel so it stops and releases the transaction lock.
                    self._cancel_proxy_transfer()
                    raise
                if result.get("success") and result.get("data"):
                    import base64

                    data = base64.b64decode(result["data"])
                    self._write_local(local_path, data)
                    self.output_json(
                        {
                            "success": True,
                            "remote_path": remote_path,
                            "local_path": local_path,
                            "size": len(data),
                            "message": f"Downloaded {len(data)} bytes via proxy",
                        }
                    )
                else:
                    self.output_json(result)
                return

            self._require_device()
            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
                max_retries=self._device_state.transfer_max_retries,
            )
            # Best-effort size lookup for the notice; never let it break the
            # actual download (e.g. stat unsupported or mocked in tests).
            size_hint = 0
            try:
                stat_ok, stat = ft.fstat(remote_path)
                if stat_ok and isinstance(stat, dict):
                    size_hint = stat.get("size", 0)
            except Exception:
                size_hint = 0
            self._transfer_notice("downloading", remote_path, size_hint)
            success, data, msg = ft.download(
                remote_path, progress_cb=self._make_progress_printer()
            )
            if not success:
                raise FPBCLIError(f"Download failed: {msg}")
            self._write_local(local_path, data)
            self.output_json(
                {
                    "success": True,
                    "remote_path": remote_path,
                    "local_path": local_path,
                    "size": len(data),
                    "message": msg,
                }
            )
        except Exception as e:
            hint = (
                self._SERIAL_LOSS_HINT if self._looks_like_serial_loss(str(e)) else None
            )
            self.output_error(f"file_download failed: {str(e)}", e, hint=hint)

    def file_upload(self, local_path: str, remote_path: str) -> None:
        """Upload a local file to device"""
        try:
            if self._proxy:
                try:
                    _sz = os.path.getsize(local_path)
                except OSError:
                    _sz = 0
                self._transfer_notice("uploading", remote_path, _sz)
                try:
                    result = self._proxy.file_upload(
                        local_path,
                        remote_path,
                        progress_cb=self._make_progress_printer(),
                    )
                except KeyboardInterrupt:
                    # Client is going away mid-transfer: tell the server to
                    # cancel so it stops and releases the transaction lock.
                    self._cancel_proxy_transfer()
                    raise
                self.output_json(result)
                return

            self._require_device()
            with open(local_path, "rb") as f:
                data = f.read()

            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
                max_retries=self._device_state.transfer_max_retries,
            )
            self._transfer_notice("uploading", remote_path, len(data))
            success, msg = ft.upload(
                data, remote_path, progress_cb=self._make_progress_printer()
            )
            if not success:
                raise FPBCLIError(f"Upload failed: {msg}")
            self.output_json(
                {
                    "success": True,
                    "local_path": local_path,
                    "remote_path": remote_path,
                    "size": len(data),
                    "message": msg,
                }
            )
        except Exception as e:
            hint = (
                self._SERIAL_LOSS_HINT if self._looks_like_serial_loss(str(e)) else None
            )
            self.output_error(f"file_upload failed: {str(e)}", e, hint=hint)

    def file_remove(self, path: str) -> None:
        """Remove a file on device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.file_remove(path))
                return

            self._require_device()
            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
            )
            success, msg = ft.fremove(path)
            if not success:
                raise FPBCLIError(f"Failed to remove: {msg}")
            self.output_json({"success": True, "path": path, "message": msg})
        except Exception as e:
            self.output_error(f"file_remove failed: {str(e)}", e)

    def file_mkdir(self, path: str) -> None:
        """Create a directory on device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.file_mkdir(path))
                return

            self._require_device()
            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
            )
            success, msg = ft.fmkdir(path)
            if not success:
                raise FPBCLIError(f"Failed to mkdir: {msg}")
            self.output_json({"success": True, "path": path, "message": msg})
        except Exception as e:
            self.output_error(f"file_mkdir failed: {str(e)}", e)

    def file_rename(self, old_path: str, new_path: str) -> None:
        """Rename a file or directory on device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.file_rename(old_path, new_path))
                return

            self._require_device()
            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
            )
            success, msg = ft.frename(old_path, new_path)
            if not success:
                raise FPBCLIError(f"Failed to rename: {msg}")
            self.output_json(
                {
                    "success": True,
                    "old_path": old_path,
                    "new_path": new_path,
                    "message": msg,
                }
            )
        except Exception as e:
            self.output_error(f"file_rename failed: {str(e)}", e)

    def mem_read(self, addr: int, length: int, fmt: str = "hex") -> None:
        """Read memory from device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.mem_read(addr, length, fmt))
                return

            self._require_device()
            self._fpb.enter_fl_mode()
            try:
                data, msg = self._fpb.read_memory(addr, length)
            finally:
                self._fpb.exit_fl_mode()

            if data is None:
                raise FPBCLIError(f"Memory read failed: {msg}")

            result = {
                "success": True,
                "addr": f"0x{addr:08X}",
                "length": length,
                "actual_length": len(data),
            }
            if fmt == "hex":
                lines = []
                for i in range(0, len(data), 16):
                    chunk = data[i : i + 16]
                    hex_part = " ".join(f"{b:02X}" for b in chunk)
                    ascii_part = "".join(
                        chr(b) if 0x20 <= b < 0x7F else "." for b in chunk
                    )
                    lines.append(f"0x{addr + i:08X}: {hex_part:<48s} {ascii_part}")
                result["hex_dump"] = "\n".join(lines)
            elif fmt == "raw":
                result["data"] = data.hex()
            elif fmt == "u32":
                result["words"] = [
                    f"0x{int.from_bytes(data[i:i+4], 'little'):08X}"
                    for i in range(0, len(data) - 3, 4)
                ]
            self.output_json(result)
        except Exception as e:
            self.output_error(f"Memory read failed: {str(e)}", e)

    def mem_write(self, addr: int, data_hex: str) -> None:
        """Write memory to device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.mem_write(addr, data_hex))
                return

            self._require_device()
            try:
                data = bytes.fromhex(data_hex)
            except ValueError:
                raise FPBCLIError(
                    f"Invalid hex data: '{data_hex}'. Use hex string like 'DEADBEEF'."
                )

            self._fpb.enter_fl_mode()
            try:
                success, error = self._fpb.write_memory(addr, data)
            finally:
                self._fpb.exit_fl_mode()

            if not success:
                raise FPBCLIError(f"Memory write failed: {error}")
            self.output_json(
                {
                    "success": True,
                    "addr": f"0x{addr:08X}",
                    "length": len(data),
                    "message": f"Wrote {len(data)} bytes to 0x{addr:08X}",
                }
            )
        except Exception as e:
            self.output_error(f"Memory write failed: {str(e)}", e)

    def mem_dump(self, addr: int, length: int, output_file: str) -> None:
        """Dump memory region to binary file"""
        try:
            if self._proxy:
                result = self._proxy.mem_read(addr, length, fmt="raw")
                if result.get("success") and result.get("data"):
                    data = bytes.fromhex(result["data"])
                    self._write_local(output_file, data)
                    self.output_json(
                        {
                            "success": True,
                            "addr": f"0x{addr:08X}",
                            "length": len(data),
                            "output_file": output_file,
                            "message": f"Dumped {len(data)} bytes to {output_file}",
                        }
                    )
                else:
                    self.output_json(result)
                return

            self._require_device()
            self._fpb.enter_fl_mode()
            try:
                data, msg = self._fpb.read_memory(addr, length)
            finally:
                self._fpb.exit_fl_mode()

            if data is None:
                raise FPBCLIError(f"Memory read failed: {msg}")
            self._write_local(output_file, data)
            self.output_json(
                {
                    "success": True,
                    "addr": f"0x{addr:08X}",
                    "length": len(data),
                    "output_file": output_file,
                    "message": f"Dumped {len(data)} bytes to {output_file}",
                }
            )
        except Exception as e:
            self.output_error(f"Memory dump failed: {str(e)}", e)
