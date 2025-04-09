# tests/unit/test_low_level_client.py
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from aiohttp import ClientError, ClientSession, WSMsgType, WSServerHandshakeError
from azure.core.credentials import AzureKeyCredential

# Import the client and its specific components needed for testing
from rtclient.low_level_client import (
    RTLowLevelClient,
    AuthenticationError,
    ClientState,
    ConnectionClosedException,
    ConnectionError,
    InvalidMessageFormatError,
)
# Import a representative server message model for testing recv parsing
from rtclient.models import SessionCreatedMessage, Session

# --- Fixtures ---

@pytest.fixture
def mock_aiohttp_session(mocker):
    """Fixture to mock the aiohttp ClientSession."""
    mock_session = mocker.MagicMock(spec=ClientSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_session.ws_connect = AsyncMock()
    mock_session.closed = False
    mock_session.close = AsyncMock()
    return mock_session

@pytest.fixture
def mock_websocket(mocker):
    """Fixture to mock the WebSocket connection object."""
    mock_ws = mocker.MagicMock()
    mock_ws.closed = False
    mock_ws.close = AsyncMock()
    mock_ws.send_str = AsyncMock()
    mock_ws.receive = AsyncMock()
    mock_ws.exception = mocker.MagicMock(return_value=None)
    mock_ws.close_code = None
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock()
    return mock_ws

@pytest.fixture
def mock_creds():
    """Provides mock credentials."""
    return AzureKeyCredential("DUMMY_KEY")

@pytest.fixture
def azure_client_config(mock_creds):
    """Config for an Azure client."""
    return {
        "url": "https://dummy.openai.azure.com",
        "key_credential": mock_creds,
        "azure_deployment": "gpt-deploy"
    }

@pytest.fixture
def openai_client_config(mock_creds):
    """Config for an OpenAI client."""
    return {
        "url": None, # Indicate OpenAI
        "key_credential": mock_creds,
        "model": "gpt-4o"
    }

# --- Test Class ---

# REMOVED @pytest.mark.asyncio from class level
class TestRTLowLevelClient:

    # === Initialization Tests (SYNC - NO asyncio decorator) ===


    def test_init_openai_success(self, openai_client_config, mock_aiohttp_session, mocker):
        """Test successful initialization for OpenAI."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        client = RTLowLevelClient(**openai_client_config)
        assert client._is_azure_openai is False
        assert client._target_url == "wss://api.openai.com/v1/realtime"
        assert client.current_state == ClientState.IDLE

    def test_init_azure_missing_creds(self, azure_client_config):
        """Test Azure init fails if credentials missing."""
        config = azure_client_config.copy()
        del config["key_credential"]
        with pytest.raises(ValueError, match="key_credential or token_credential"):
            RTLowLevelClient(**config)

    def test_init_azure_missing_deployment(self, azure_client_config):
        """Test Azure init fails if deployment missing."""
        config = azure_client_config.copy()
        del config["azure_deployment"]
        with pytest.raises(ValueError, match="azure_deployment is required"):
            RTLowLevelClient(**config)

    def test_init_openai_missing_creds(self, openai_client_config):
        """Test OpenAI init fails if credentials missing."""
        config = openai_client_config.copy()
        del config["key_credential"]
        with pytest.raises(ValueError, match="key_credential is required"):
            RTLowLevelClient(**config)

    def test_init_openai_missing_model(self, openai_client_config):
        """Test OpenAI init fails if model missing."""
        config = openai_client_config.copy()
        del config["model"]
        with pytest.raises(ValueError, match="model is required"):
            RTLowLevelClient(**config)

    # === Connection Tests (ASYNC - ADDED asyncio decorator) ===

    @pytest.mark.asyncio
    async def test_connect_success_openai(self, openai_client_config, mock_aiohttp_session, mock_websocket, mocker):
        """Test successful connection flow for OpenAI."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mock_aiohttp_session.ws_connect.return_value = mock_websocket
        mocker.patch('rtclient.low_level_client.uuid.uuid4', return_value=uuid.UUID('12345678-1234-5678-1234-567812345678'))
        mocker.patch('rtclient.low_level_client.get_user_agent', return_value='TestAgent/1.0')

        client = RTLowLevelClient(**openai_client_config)
        assert client.current_state == ClientState.IDLE

        await client.connect()

        assert client.current_state == ClientState.CONNECTED
        assert client._ws == mock_websocket
        mock_aiohttp_session.ws_connect.assert_called_once()
        call_args, call_kwargs = mock_aiohttp_session.ws_connect.call_args
        assert call_args[0] == "wss://api.openai.com/v1/realtime" # Check URL
        assert call_kwargs['headers']['Authorization'] == "Bearer DUMMY_KEY"
        assert call_kwargs['headers']['User-Agent'] == 'TestAgent/1.0'
        assert call_kwargs['headers']['openai-beta'] == 'realtime=v1'
        assert call_kwargs['params'] == {"model": "gpt-4o"}
        assert 'heartbeat' in call_kwargs # Check heartbeat is passed

    @pytest.mark.asyncio
    async def test_connect_auth_failure(self, openai_client_config, mock_aiohttp_session, mocker):
        """Test connection fails if auth header generation fails."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mocker.patch.object(RTLowLevelClient, '_get_auth_headers', side_effect=AuthenticationError("Test Auth Fail"))

        client = RTLowLevelClient(**openai_client_config)

        with pytest.raises(AuthenticationError, match="Test Auth Fail"):
            await client.connect()

        assert client.current_state == ClientState.CLOSED

    @pytest.mark.asyncio
    async def test_connect_handshake_failure(self, openai_client_config, mock_aiohttp_session, mocker):
        """Test connection fails on WSServerHandshakeError."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mock_aiohttp_session.ws_connect.side_effect = WSServerHandshakeError(
            request_info=mocker.MagicMock(), history=(), status=401,
            message="Unauthorized", headers={}
        )

        client = RTLowLevelClient(**openai_client_config)

        with pytest.raises(ConnectionError, match="Server handshake failed with status 401"):
            await client.connect()

        assert client.current_state == ClientState.CLOSED

    @pytest.mark.asyncio
    async def test_connect_other_client_error(self, openai_client_config, mock_aiohttp_session, mocker):
        """Test connection fails on other ClientErrors (e.g., DNS)."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mock_aiohttp_session.ws_connect.side_effect = ClientError("DNS Lookup Failed")

        client = RTLowLevelClient(**openai_client_config)

        with pytest.raises(ConnectionError, match="Connection establishment failed: DNS Lookup Failed"):
            await client.connect()

        assert client.current_state == ClientState.CLOSED

    # === Retry Tests ===

    @pytest.mark.asyncio
    async def test_connect_retry_success(self, openai_client_config, mock_aiohttp_session, mock_websocket, mocker):
        """Test connection succeeds after a few retries."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mocker.patch('rtclient.low_level_client.uuid.uuid4')
        mocker.patch('rtclient.low_level_client.get_user_agent')
        mock_aiohttp_session.ws_connect.side_effect = [
            ClientError("Temporary Network Glitch"),
            ClientError("Another Glitch"),
            mock_websocket
        ]
        mock_sleep = mocker.patch('asyncio.sleep', return_value=None)

        retry_config = {"max_attempts": 3, "initial_delay": 0.01}
        client = RTLowLevelClient(**openai_client_config, connect_retry_config=retry_config)

        await client.connect()

        assert client.current_state == ClientState.CONNECTED
        assert mock_aiohttp_session.ws_connect.call_count == 3
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_connect_retry_failure(self, openai_client_config, mock_aiohttp_session, mocker):
        """Test connection fails permanently after exhausting retries."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mocker.patch('rtclient.low_level_client.uuid.uuid4')
        mocker.patch('rtclient.low_level_client.get_user_agent')
        mock_aiohttp_session.ws_connect.side_effect = ClientError("Persistent Failure")
        mock_sleep = mocker.patch('asyncio.sleep', return_value=None)

        retry_config = {"max_attempts": 2, "initial_delay": 0.01}
        client = RTLowLevelClient(**openai_client_config, connect_retry_config=retry_config)

        with pytest.raises(ConnectionError, match="Persistent Failure"):
            await client.connect()

        assert client.current_state == ClientState.CLOSED
        assert mock_aiohttp_session.ws_connect.call_count == 2
        assert mock_sleep.call_count == 1

    # === Send / Receive Tests (Basic) ===

    @pytest.mark.asyncio
    async def test_send_success(self, openai_client_config, mock_aiohttp_session, mock_websocket, mocker):
        """Test sending a message successfully."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mock_aiohttp_session.ws_connect.return_value = mock_websocket
        client = RTLowLevelClient(**openai_client_config)
        await client.connect()

        dummy_message = MagicMock()
        dummy_message.type = "input_audio_buffer.append"
        dummy_message.model_dump_json = MagicMock(return_value='{"type": "input_audio_buffer.append", "audio": "..."}')

        await client.send(dummy_message)

        mock_websocket.send_str.assert_called_once_with('{"type": "input_audio_buffer.append", "audio": "..."}')

    @pytest.mark.asyncio
    async def test_recv_success(self, openai_client_config, mock_aiohttp_session, mock_websocket, mocker):
        """Test receiving and parsing a message successfully."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mock_aiohttp_session.ws_connect.return_value = mock_websocket
        # Mock create_message_from_dict used internally by the client
        mock_create_message = mocker.patch('rtclient.low_level_client.create_message_from_dict')
        # Make the mock return a specific known type
        expected_message = SessionCreatedMessage(event_id="evt1", type="session.created", session=mocker.MagicMock(spec=Session))
        mock_create_message.return_value = expected_message

        mock_ws_message = MagicMock(type=WSMsgType.TEXT)
        mock_ws_message.data = '{"type": "session.created", "event_id": "evt1", "session": {"id": "s1"}}' # Sample data
        mock_websocket.receive.return_value = mock_ws_message

        client = RTLowLevelClient(**openai_client_config)
        await client.connect()

        received_msg = await client.recv()

        mock_create_message.assert_called_once_with({"type": "session.created", "event_id": "evt1", "session": {"id": "s1"}})
        assert received_msg == expected_message
        assert isinstance(received_msg, SessionCreatedMessage)

    @pytest.mark.asyncio
    async def test_recv_invalid_json(self, openai_client_config, mock_aiohttp_session, mock_websocket, mocker):
        """Test receiving invalid JSON raises InvalidMessageFormatError."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mock_aiohttp_session.ws_connect.return_value = mock_websocket

        mock_ws_message = MagicMock(type=WSMsgType.TEXT)
        mock_ws_message.data = '{"type": "session.created", "event_id": "evt1", "session": {' # Malformed
        mock_websocket.receive.return_value = mock_ws_message

        client = RTLowLevelClient(**openai_client_config)
        await client.connect()

        with pytest.raises(InvalidMessageFormatError, match="Invalid JSON received"):
            await client.recv()

    @pytest.mark.asyncio
    async def test_recv_websocket_close_message(self, openai_client_config, mock_aiohttp_session, mock_websocket, mocker):
        """Test receiving a CLOSE message raises ConnectionClosedException."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mock_aiohttp_session.ws_connect.return_value = mock_websocket
        mock_handle_disconnect = mocker.patch.object(RTLowLevelClient, '_handle_disconnection', AsyncMock())

        mock_ws_message = MagicMock(type=WSMsgType.CLOSE)
        mock_ws_message.data = 'Server closing'
        mock_websocket.receive.return_value = mock_ws_message
        mock_websocket.close_code = 1000

        client = RTLowLevelClient(**openai_client_config)
        await client.connect()

        # CHANGED: Use raw string for regex match pattern
        with pytest.raises(ConnectionClosedException, match=r"WebSocket closed by server \(code: 1000\)"):
            await client.recv()

        mock_handle_disconnect.assert_called_once()


    # === Disconnection / Reconnection Tests ===

    @pytest.mark.asyncio
    async def test_send_connection_reset_triggers_reconnect_and_retry_send(self, openai_client_config, mock_aiohttp_session, mock_websocket, mocker):
        """Test ConnectionResetError on send triggers reconnect and retries send."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mocker.patch('rtclient.low_level_client.uuid.uuid4')
        mocker.patch('rtclient.low_level_client.get_user_agent')

        # Make first send fail, second succeed (after reconnect)
        mock_websocket.send_str.side_effect = ConnectionResetError("Connection broken during send")

        # Setup new websocket for successful reconnect
        new_mock_websocket = MagicMock()
        new_mock_websocket.send_str = AsyncMock() # Mock send on the new socket
        new_mock_websocket.closed = False

        # Setup ws_connect side effect for initial and reconnect
        mock_aiohttp_session.ws_connect.side_effect = [mock_websocket, new_mock_websocket]
        mocker.patch('asyncio.sleep', return_value=None)

        client = RTLowLevelClient(**openai_client_config, connect_retry_config={"max_attempts": 2})
        await client.connect()

        dummy_message = MagicMock(type="test.msg")
        dummy_message.model_dump_json = MagicMock(return_value='{"type":"test.msg"}')

        # This send should fail, trigger reconnect, and retry the send on the new socket
        await client.send(dummy_message)

        assert client.current_state == ClientState.CONNECTED
        assert mock_aiohttp_session.ws_connect.call_count == 2
        assert mock_websocket.send_str.call_count == 1 # Failed send on old socket
        new_mock_websocket.send_str.assert_called_once_with('{"type":"test.msg"}')


    # === Close and Context Manager Tests ===

    @pytest.mark.asyncio
    async def test_close_method(self, openai_client_config, mock_aiohttp_session, mock_websocket, mocker):
        """Test the close method cleans up resources."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mock_aiohttp_session.ws_connect.return_value = mock_websocket

        client = RTLowLevelClient(**openai_client_config)
        await client.connect()
        assert client.current_state == ClientState.CONNECTED

        await client.close()

        assert client.current_state == ClientState.CLOSED
        mock_websocket.close.assert_called_once()
        mock_aiohttp_session.close.assert_called_once()
        assert client._ws is None

    @pytest.mark.asyncio
    async def test_close_idempotency(self, openai_client_config, mock_aiohttp_session, mock_websocket, mocker):
        """Test calling close multiple times is safe."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mock_aiohttp_session.ws_connect.return_value = mock_websocket

        client = RTLowLevelClient(**openai_client_config)
        await client.connect()
        await client.close()
        # Call close again
        await client.close()

        assert client.current_state == ClientState.CLOSED
        mock_websocket.close.assert_called_once()
        mock_aiohttp_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager(self, openai_client_config, mock_aiohttp_session, mock_websocket, mocker):
        """Test the client works as an async context manager."""
        mocker.patch('rtclient.low_level_client.ClientSession', return_value=mock_aiohttp_session)
        mock_aiohttp_session.ws_connect.return_value = mock_websocket
        # Spy on the *instance's* methods after creation
        client = RTLowLevelClient(**openai_client_config)
        connect_spy = mocker.spy(client, "connect")
        close_spy = mocker.spy(client, "close")


        async with client:
            assert client.current_state == ClientState.CONNECTED
            connect_spy.assert_called_once()
            assert close_spy.call_count == 0 # close() within connect doesn't count here if fixed

        assert client.current_state == ClientState.CLOSED
        close_spy.assert_called_once()