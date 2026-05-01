def normalize_ui_response(
    response,
    *,
    success,
    require_result_code=False,
    default_fields=None,
):
    response = response or {}
    default_fields = dict(default_fields or {})

    if not isinstance(response, dict):
        return {
            "result_code": "CLIENT_ERROR",
            "result_message": str(response),
            "reason_code": "CLIENT_RESPONSE_INVALID",
            **default_fields,
        }

    if (not success or require_result_code) and not response.get("result_code"):
        return {
            **response,
            "result_code": "CLIENT_ERROR",
            "reason_code": response.get("reason_code") or "CLIENT_ERROR",
        }

    return response


__all__ = ["normalize_ui_response"]
