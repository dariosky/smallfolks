from fastapi.staticfiles import StaticFiles


class ImmutableStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict[str, object]):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers.setdefault(
                "Cache-Control",
                "public, max-age=31536000, immutable",
            )
        return response
