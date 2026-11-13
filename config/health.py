from django.db import connection
from django.http import JsonResponse


def health(request):
    """Docker/balanser tekshiruvi: ilova ishlayaptimi va baza javob beryaptimi."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "db_error"}, status=503)
    return JsonResponse({"status": "ok"})
