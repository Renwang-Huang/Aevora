"""Non-secret model provider configuration, independent of benchmark episodes.

The legacy ChatGPT ``ModelBroker`` remains an optional, separate contract. This
module does not read an identity file or turn an API key into ChatGPT OAuth.
The API root is explicit: discovering that a gateway uses /v1 must happen in a
trusted handshake, never by silently trying different upstreams during a run.
"""
from dataclasses import dataclass
import re
from urllib.parse import urlsplit


GATEWAY_URL = "https://api.renwang-huang.top"
GATEWAY_MODEL = "gpt-5.6-terra"
GATEWAY_EFFORT = "max"
DEEPSEEK_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-flash"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
_UPSTREAMS = {
    "gateway": "api.renwang-huang.top",
    "deepseek": "api.deepseek.com",
}


@dataclass(frozen=True)
class ProviderConfig:
    """A nominated gateway configuration; capability claims need live evidence.

    ``effort`` is the explicitly selected effort sent to the gateway.
    ``requested_effort`` retains the experimental request when an operator has
    explicitly selected a verified alternative, for example max -> xhigh.
    Neither field establishes that the upstream actually honored the request.
    """

    provider_id: str = "gateway"
    base_url: str = GATEWAY_URL
    model: str = GATEWAY_MODEL
    effort: str = GATEWAY_EFFORT
    requested_effort: str | None = None

    def __post_init__(self):
        if not _ID.fullmatch(self.provider_id) or not _ID.fullmatch(self.model):
            raise ValueError("Provider and model IDs must be bounded identifiers")
        if self.effort not in _EFFORTS or (
                self.requested_effort is not None and self.requested_effort not in _EFFORTS):
            raise ValueError("Unsupported nominated reasoning effort")
        parsed = urlsplit(self.base_url)
        try:
            port = parsed.port
        except ValueError:
            raise ValueError("Invalid gateway endpoint") from None
        expected_host = _UPSTREAMS.get(self.provider_id)
        if expected_host is None:
            raise ValueError("Unsupported model provider")
        if (parsed.scheme != "https" or parsed.hostname != expected_host
                or port not in (None, 443) or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ("", "/", "/v1", "/v1/")):
            raise ValueError("Provider must use its authorized HTTPS endpoint and an explicit API root")
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))

    @property
    def requested_model(self) -> str:
        return self.model

    @property
    def endpoint_hostname(self) -> str:
        return urlsplit(self.base_url).hostname

    @property
    def metadata(self) -> dict:
        return {"provider_id": self.provider_id, "upstream_provider": self.provider_id,
                "endpoint_hostname": self.endpoint_hostname,
                "api_root": urlsplit(self.base_url).path or "/",
                "requested_model": self.model,
                "requested_effort": self.requested_effort or self.effort,
                "selected_effort": self.effort, "wire_api": "responses",
                "effective_model": "UNVERIFIED", "effective_effort": "UNVERIFIED"}


GatewayProvider = ProviderConfig


def gateway_provider(*, base_url: str = GATEWAY_URL, model: str = GATEWAY_MODEL,
                     effort: str = GATEWAY_EFFORT,
                     requested_effort: str | None = None) -> ProviderConfig:
    return ProviderConfig(provider_id="gateway", base_url=base_url, model=model, effort=effort,
                          requested_effort=requested_effort)


def deepseek_provider(*, base_url: str = DEEPSEEK_URL, model: str = DEEPSEEK_MODEL,
                      effort: str = GATEWAY_EFFORT,
                      requested_effort: str | None = None) -> ProviderConfig:
    return ProviderConfig(provider_id="deepseek", base_url=base_url, model=model, effort=effort,
                          requested_effort=requested_effort)
