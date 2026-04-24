from typing import List, Dict, Any, Optional


class AgendaResponseBuilder:

    @staticmethod
    def build(
        status: str,
        ok: List[Dict[str, Any]],
        fail: List[Dict[str, Any]],
        meta: Optional[Dict[str, Any]] = None,
    ) -> dict:

        if meta is None:
            meta = {
                "total": len(ok) + len(fail),
                "ok": len(ok),
                "fail": len(fail),
            }

        return {
            "status": status,
            "ok": ok,
            "fail": fail,
            "meta": meta,
        }