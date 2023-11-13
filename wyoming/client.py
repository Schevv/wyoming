import asyncio
from abc import ABC
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

from .event import (
    Event,
    async_get_stdin,
    async_get_stdout,
    async_read_event,
    async_write_event,
)


class AsyncClient(ABC):
    """Base class for Wyoming async client."""

    def __init__(self) -> None:
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def read_event(self) -> Optional[Event]:
        assert self._reader is not None
        return await async_read_event(self._reader)

    async def write_event(self, event: Event):
        assert self._writer is not None
        await async_write_event(event, self._writer)

    @staticmethod
    def from_uri(uri: str) -> "AsyncClient":
        result = urlparse(uri)

        if result.scheme == "unix":
            return AsyncUnixClient(result.path)

        if result.scheme == "tcp":
            host, port_str = result.netloc.split(":")
            port = int(port_str)
            return AsyncTcpClient(host, port)

        if result.scheme == "stdio":
            return AsyncStdioClient()

        raise ValueError("Only 'stdio://', 'unix://', or 'tcp://' are supported")


class AsyncTcpClient(AsyncClient):
    """TCP Wyoming client."""

    def __init__(self, host: str, port: int) -> None:
        super().__init__()

        self.host = host
        self.port = port

    async def __aenter__(self):
        self._reader, self._writer = await asyncio.open_connection(
            host=self.host,
            port=self.port,
        )

        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        writer = self._writer
        self._reader = None
        self._writer = None

        if writer is not None:
            writer.close()
            await writer.wait_closed()


class AsyncUnixClient(AsyncClient):
    """Unix domain socket Wyoming client."""

    def __init__(self, socket_path: Union[str, Path]) -> None:
        super().__init__()

        self.socket_path = socket_path

    async def __aenter__(self):
        self._reader, self._writer = await asyncio.open_unix_connection(
            path=self.socket_path
        )

        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        writer = self._writer
        self._reader = None
        self._writer = None

        if writer is not None:
            writer.close()
            await writer.wait_closed()


class AsyncStdioClient(AsyncClient):
    """Standard output Wyoming client."""

    def __init__(self) -> None:
        super().__init__()

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def read_event(self) -> Optional[Event]:
        if self._reader is None:
            self._reader = await async_get_stdin()

        assert self._reader is not None
        return await async_read_event(self._reader)

    async def write_event(self, event: Event):
        if self._writer is None:
            self._writer = await async_get_stdout()

        assert self._writer is not None
        await async_write_event(event, self._writer)
