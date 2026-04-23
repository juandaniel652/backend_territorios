from typing import List, Dict, Any


class AgendaResponseBuilder:

    @staticmethod
    def build(
        status: str,
        items_ok: List[Dict[str, Any]],
        items_fail: List[Dict[str, Any]],
    ) -> dict:

        total = len(items_ok) + len(items_fail)

        return {
            "status": status,
            "items_ok": items_ok,
            "items_fail": items_fail,
            "meta": {
                "total": total,
                "ok": len(items_ok),
                "fail": len(items_fail),
            }
        }