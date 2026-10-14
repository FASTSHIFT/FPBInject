"""exec command handler for the FPB CLI.

Kept in its own module so cli.fpb_cli stays under the file-size limit. The
method is mixed into :class:`FPBCLI` and relies on its attributes (``_proxy``,
``_fpb``) and helpers (``output_json``, ``output_error``, ``_require_device``).
"""

from typing import Optional

from fpbinject.cli.errors import FPBCLIError
from fpbinject.core.exec_client import ExecArgumentError


class ExecCommandsMixin:
    """Run a shell command on the device through the fl exec command."""

    def exec_cmd(self, cmd: str, timeout: Optional[float] = None) -> bool:
        """Run ``cmd`` on the device and print the result as JSON.

        Retries follow the shared ``--transfer-max-retries`` setting.

        Returns:
            True if the command ran and its result was verified (the command's
            own exit status is the ``ret`` field), False otherwise so the
            caller can set a non-zero process exit code.
        """
        try:
            if self._proxy:
                result = self._proxy.exec_cmd(cmd, timeout=timeout)
            else:
                self._require_device()
                with self._fpb.fl_session():
                    result = self._fpb.exec_cmd(cmd, timeout=timeout)
        except ExecArgumentError as e:
            raise FPBCLIError(str(e))
        except FPBCLIError:
            raise
        except Exception as e:
            self.output_error(f"exec failed: {str(e)}", e)
            return False

        self.output_json(result)
        return bool(result.get("success"))
