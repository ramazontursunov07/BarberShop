"""Django backend bilan muloqot (HTTP). Bot hech qachon DB'ga to'g'ridan-to'g'ri tegmaydi."""
import httpx


class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


class NotLinked(ApiError):
    """Bu Telegram akkaunt hali telefon raqamga bog'lanmagan."""


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200]
    if isinstance(body, dict):
        return str(body.get("detail") or body)
    return str(body)


class BackendClient:
    def __init__(self, base_url: str, secret: str):
        self._secret = secret
        # AI javobi ko'p qadamli bo'lishi mumkin (tool'lar), shuning uchun timeout uzun
        self._http = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(90.0, connect=10.0))

    async def get_token(
            self,
            telegram_id: int,
            phone: str | None = None,
            first_name: str = "",
            last_name: str = "",
    ) -> str:
        payload: dict = {"telegram_id": telegram_id}
        if phone:
            payload.update({"phone": phone, "first_name": first_name, "last_name": last_name})
        resp = await self._http.post(
            "/api/users/telegram/auth/", json=payload, headers={"X-Bot-Secret": self._secret}
        )
        if resp.status_code == 404:
            raise NotLinked(404, _detail(resp))
        if resp.status_code != 200:
            raise ApiError(resp.status_code, _detail(resp))
        return resp.json()["access"]

    async def chat(self, token: str, message: str, history: list[dict]) -> str:
        resp = await self._http.post(
            "/api/ai/chat/",
            json={"message": message, "history": history},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            raise ApiError(resp.status_code, _detail(resp))
        return resp.json()["reply"]

    async def close(self) -> None:
        await self._http.aclose()
