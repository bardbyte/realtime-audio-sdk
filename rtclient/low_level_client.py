# import json
# import os
# import uuid
# import asyncio
# import logging
# from enum import Enum

# from collections.abc import AsyncIterator
# from typing import Optional, Dict, Any

# from aiohttp import ClientSession, WSMsgType, WSServerHandshakeError
# from azure.core.credentials import AzureKeyCredential
# from azure.core.credentials_async import AsyncTokenCredential

# from rtclient.models import ServerMessageType, UserMessageType, create_message_from_dict
# from rtclient.util.user_agent import get_user_agent
# from rtclient.util.retry import retry_async

# class ConnectionError(Exception): # Enhanced
#     def __init__(self, message: str, status: Optional[int] = None, headers=None):
#         super().__init__(message)
#         self.status = status
#         self.headers = headers

# class AuthenticationError(ConnectionError): pass
# class ConnectionClosedException(Exception): pass
# class InvalidMessageFormatError(Exception): pass

# # --- Define Client States ---
# class ClientState(Enum):
#     IDLE = 0
#     CONNECTING = 1
#     CONNECTED = 2
#     RECONNECTING = 3
#     CLOSING = 4
#     CLOSED = 5

# # --- Setup Logger ---
# logger = logging.getLogger(__name__)
# # Configure logging elsewhere in your app, e.g.:
# # logging.basicConfig(level=logging.INFO)

# class RTLowLevelClient:
#     def __init__(
#         self,
#         url: Optional[str] = None,
#         token_credential: Optional[AsyncTokenCredential] = None,
#         key_credential: Optional[AzureKeyCredential] = None,
#         model: Optional[str] = None,
#         azure_deployment: Optional[str] = None,
#     ):
#         self._is_azure_openai = url is not None
#         if self._is_azure_openai:
#             if key_credential is None and token_credential is None:
#                 raise ValueError("key_credential or token_credential is required for Azure OpenAI")
#             if azure_deployment is None:
#                 raise ValueError("azure_deployment is required for Azure OpenAI")
#         else:
#             if key_credential is None:
#                 raise ValueError("key_credential is required for OpenAI")
#             if model is None:
#                 raise ValueError("model is required for OpenAI")

#         self._url = url if self._is_azure_openai else "wss://api.openai.com"
#         self._token_credential = token_credential
#         self._key_credential = key_credential
#         self._session = ClientSession(base_url=self._url)
#         self._model = model
#         self._azure_deployment = azure_deployment
#         self.request_id: Optional[uuid.UUID] = None

#     async def _get_auth(self):
#         if self._token_credential:
#             scope = "https://cognitiveservices.azure.com/.default"
#             token = await self._token_credential.get_token(scope)
#             return {"Authorization": f"Bearer {token.token}"}
#         elif self._key_credential:
#             return {"api-key": self._key_credential.key}
#         else:
#             return {}

#     @staticmethod
#     def _get_azure_params():
#         api_version = os.getenv("AZURE_OPENAI_API_VERSION")
#         path = os.getenv("AZURE_OPENAI_PATH")
#         return (
#             "2024-10-01-preview" if api_version is None else api_version,
#             "/openai/realtime" if path is None else path,
#         )

#     async def connect(self):
#         try:
#             self.request_id = uuid.uuid4()
#             if self._is_azure_openai:
#                 api_version, path = RTLowLevelClient._get_azure_params()
#                 auth_headers = await self._get_auth()
#                 headers = {
#                     "x-ms-client-request-id": str(self.request_id),
#                     "User-Agent": get_user_agent(),
#                     **auth_headers,
#                 }
#                 self.ws = await self._session.ws_connect(
#                     path,
#                     headers=headers,
#                     params={"deployment": self._azure_deployment, "api-version": api_version},
#                 )
#             else:
#                 headers = {
#                     "Authorization": f"Bearer {self._key_credential.key}",
#                     "openai-beta": "realtime=v1",
#                     "User-Agent": get_user_agent(),
#                 }
#                 self.ws = await self._session.ws_connect("/v1/realtime", headers=headers, params={"model": self._model})
#         except WSServerHandshakeError as e:
#             await self._session.close()
#             error_message = f"Received status code {e.status} from the server"
#             raise ConnectionError(error_message, e.headers) from e

#     async def send(self, message: UserMessageType):
#         message._is_azure = self._is_azure_openai
#         message_json = message.model_dump_json(exclude_unset=True)
#         await self.ws.send_str(message_json)

#     async def recv(self) -> ServerMessageType | None:
#         if self.ws.closed:
#             return None
#         websocket_message = await self.ws.receive()
#         if websocket_message.type == WSMsgType.TEXT:
#             data = json.loads(websocket_message.data)
#             msg = create_message_from_dict(data)
#             return msg
#         else:
#             return None

#     def __aiter__(self) -> AsyncIterator[ServerMessageType | None]:
#         return self

#     async def __anext__(self):
#         message = await self.recv()
#         if message is None:
#             raise StopAsyncIteration
#         return message

#     async def close(self):
#         await self.ws.close()
#         await self._session.close()

#     @property
#     def closed(self) -> bool:
#         return self.ws.closed

#     async def __aenter__(self):
#         await self.connect()
#         return self

#     async def __aexit__(self, *args):
#         await self.close()
import json
import os
import uuid
import asyncio
import logging
from enum import Enum
from collections.abc import AsyncIterator
from typing import Optional, Dict, Any

from aiohttp import ClientSession, WSMsgType, WSServerHandshakeError, ClientError
from azure.core.credentials import AzureKeyCredential
from azure.core.credentials_async import AsyncTokenCredential
# Assuming pydantic models exist
from rtclient.models import ServerMessageType, UserMessageType, create_message_from_dict
from rtclient.util.user_agent import get_user_agent
# Import your retry decorator
from rtclient.util.retry import retry_async

# Define specific exceptions for clarity
class ConnectionError(Exception):
    def __init__(self, message: str, status: Optional[int] = None, headers=None):
        super().__init__(message)
        self.status = status
        self.headers = headers

class AuthenticationError(ConnectionError): pass
class ConnectionClosedException(Exception): pass
class InvalidMessageFormatError(Exception): pass

# Use Enum for clear states
class ClientState(Enum):
    IDLE = 0
    CONNECTING = 1
    CONNECTED = 2
    RECONNECTING = 3
    CLOSING = 4
    CLOSED = 5

logger = logging.getLogger(__name__)

class RTLowLevelClient:
    def __init__(
        self,
        # Credentials should be handled more securely, maybe via explicit args or config object
        url: Optional[str] = None, # If None, assumes OpenAI wss://api.openai.com
        token_credential: Optional[AsyncTokenCredential] = None,
        key_credential: Optional[AzureKeyCredential] = None, # Used for Azure OR OpenAI key
        model: Optional[str] = None, # OpenAI model
        azure_deployment: Optional[str] = None, # Azure deployment ID
        # Explicit config > env vars inside methods
        azure_api_version: str = "2024-10-01-preview",
        azure_api_path: str = "/openai/realtime",
        # Allow passing a session for potential reuse/customization
        session: Optional[ClientSession] = None,
        # Retry configuration could be passed in too
        connect_retry_config: Optional[Dict[str, Any]] = None,
    ):
        self._is_azure_openai = url is not None
        self._target_url = url if self._is_azure_openai else "wss://api.openai.com/v1/realtime" # More specific OpenAI path

        # === Validation ===
        if self._is_azure_openai:
            if key_credential is None and token_credential is None:
                raise ValueError("key_credential or token_credential is required for Azure OpenAI")
            if azure_deployment is None:
                raise ValueError("azure_deployment is required for Azure OpenAI")
            self._auth_credential = token_credential if token_credential else key_credential
        else: # OpenAI
            if key_credential is None:
                raise ValueError("key_credential is required for OpenAI (use AzureKeyCredential wrapper)")
            if model is None:
                raise ValueError("model is required for OpenAI")
            self._auth_credential = key_credential

        self._model = model
        self._azure_deployment = azure_deployment
        self._azure_api_version = azure_api_version
        self._azure_api_path = azure_api_path

        # === State & Resources ===
        self._session = session or ClientSession() # Use passed session or create one
        self._manage_session = session is None # Flag if we need to close the session ourselves
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._state = ClientState.IDLE
        self.request_id: Optional[uuid.UUID] = None # Keep for Azure, maybe generate per-connection attempt

        # === Retry Configuration ===
        # Sensible defaults if not provided
        self._retry_config = connect_retry_config or {
             "max_attempts": 5, "initial_delay": 0.5, "max_delay": 10.0,
             "backoff_factor": 2.0, "jitter": 0.1,
             # Retry on common transient network/server errors
             "retry_on_exceptions": (ConnectionError, ClientError, asyncio.TimeoutError, WSServerHandshakeError)
        }
        # Dynamically apply the decorator to the connect method instance
        # This allows passing config via __init__
        self.connect = retry_async(**self._retry_config)(self._connect_internal)

        logger.info(f"RTLowLevelClient initialized for {'Azure' if self._is_azure_openai else 'OpenAI'}. Target: {self._target_url}")


    async def _get_auth_headers(self) -> Dict[str, str]:
        # Simplified auth logic
        try:
            if isinstance(self._auth_credential, AsyncTokenCredential):
                 scope = "https://cognitiveservices.azure.com/.default"
                 token = await self._auth_credential.get_token(scope)
                 return {"Authorization": f"Bearer {token.token}"}
            elif isinstance(self._auth_credential, AzureKeyCredential):
                 # Use api-key for Azure, Authorization: Bearer for OpenAI
                 if self._is_azure_openai:
                     return {"api-key": self._auth_credential.key}
                 else:
                     return {"Authorization": f"Bearer {self._auth_credential.key}"}
            else:
                 logger.error("Invalid credential type provided.")
                 raise AuthenticationError("Invalid credential configuration.")
        except Exception as e:
            logger.exception("Failed to get authentication token/key.")
            raise AuthenticationError(f"Authentication failed: {e}") from e

    # This is the method the decorator will wrap
    async def _connect_internal(self):
        if self._state not in (ClientState.IDLE, ClientState.CLOSED, ClientState.RECONNECTING):
            logger.warning(f"Connection attempt ignored in state: {self._state.name}")
            return # Or raise an error?

        # await self.close() # Ensure any previous connection is cleaned up before trying again

        self.request_id = uuid.uuid4() # New ID for each connection attempt
        logger.info(f"Attempting to connect (request_id: {self.request_id}). State: {self._state.name} -> CONNECTING")
        self._state = ClientState.CONNECTING

        try:
            auth_headers = await self._get_auth_headers()
            headers = {
                "User-Agent": get_user_agent(),
                **auth_headers,
            }
            params = {}

            if self._is_azure_openai:
                connect_url = self._target_url  # Combine base and path
                headers["x-ms-client-request-id"] = str(self.request_id)
                params = {"deployment": self._azure_deployment, "api-version": self._azure_api_version}
            else: # OpenAI
                connect_url = self._target_url # URL already includes /v1/realtime
                headers["openai-beta"] = "realtime=v1" # Assuming this header is still needed
                params = {"model": self._model}

            logger.debug(f"Connecting to {connect_url} with params: {params}")
            self._ws = await self._session.ws_connect(
                connect_url,
                headers=headers,
                params=params,
                heartbeat=30 # Example: Add heartbeat to detect dead connections sooner
            )
            self._state = ClientState.CONNECTED
            logger.info(f"WebSocket connection established. State: {self._state.name}")

        # Catch specific errors for better logging/handling before retry decorator takes over
        except WSServerHandshakeError as e:
            logger.error(f"WebSocket handshake failed: Status {e.status}, Headers: {e.headers}", exc_info=True)
            self._state = ClientState.CLOSED # Failed connection attempt
            # Raise custom error the decorator can catch
            raise ConnectionError(f"Server handshake failed with status {e.status}", status=e.status, headers=e.headers) from e
        except ClientError as e: # Catches ClientConnectorError, etc.
            logger.error(f"Client connection error: {e}", exc_info=True)
            self._state = ClientState.CLOSED
            raise ConnectionError(f"Connection establishment failed: {e}") from e
        except AuthenticationError as e: # Propagate auth errors
             self._state = ClientState.CLOSED
             raise e
        except Exception as e:
            logger.exception("An unexpected error occurred during connection.")
            self._state = ClientState.CLOSED
            # Raise a generic connection error the decorator might retry on
            raise ConnectionError(f"Unexpected connection error: {e}") from e


    async def send(self, message: UserMessageType):
        if self._state != ClientState.CONNECTED:
             logger.error(f"Cannot send message in state: {self._state.name}. Attempting reconnect...")
             # Trigger reconnection before sending
             await self._ensure_connected() # This will block until connected or fail

        if self._state == ClientState.CONNECTED and self._ws and not self._ws.closed:
            try:
                message._is_azure = self._is_azure_openai # Set flag based on connection type
                message_json = message.model_dump_json(exclude_unset=True)
                await self._ws.send_str(message_json)
                logger.debug(f"Message sent: {message.type}") # Log type, not content by default
            except (ConnectionResetError) as e:
                logger.error(f"Send failed due to connection error: {e}. State: {self._state.name}. Attempting reconnect.", exc_info=True)
                self._state = ClientState.RECONNECTING # Mark for reconnect
                await self._handle_disconnection()
                # After handling disconnection, retry the send (or raise)
                await self.send(message) # Recursive call AFTER potential reconnect
            except Exception as e:
                logger.exception(f"Failed to send message: {message.type}")
                # Decide if this error is recoverable or should be raised
                raise # Re-raise unexpected errors for now
        else:
            logger.error(f"WebSocket not connected or available in state {self._state.name}. Attempting reconnect...")
            # Handle case where ws is None or closed unexpectedly
            await self._handle_disconnection()
            await self.send(message) # Retry send after handling

    async def recv(self) -> ServerMessageType:
        if self._state != ClientState.CONNECTED:
             logger.warning(f"Cannot receive message in state: {self._state.name}. Attempting reconnect...")
             await self._ensure_connected()

        if self._state == ClientState.CONNECTED and self._ws and not self._ws.closed:
            try:
                websocket_message = await self._ws.receive()

                if websocket_message.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(websocket_message.data)
                        msg = create_message_from_dict(data)
                        logger.debug(f"Message received: {msg.type}")
                        return msg
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode JSON message: {websocket_message.data[:100]}...", exc_info=True)
                        raise InvalidMessageFormatError(f"Invalid JSON received from server: {e}") from e
                elif websocket_message.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error message received: {websocket_message.data}", exc_info=True)
                    # Attempt to reconnect on error frames
                    self._state = ClientState.RECONNECTING
                    await self._handle_disconnection()
                    # Raise after handling so iteration stops unless reconnect is immediate
                    raise ConnectionClosedException("WebSocket error frame received.")
                elif websocket_message.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
                    logger.warning(f"WebSocket closed message received: Code {self._ws.close_code}, Data: {websocket_message.data}")
                    # Treat as disconnection
                    self._state = ClientState.RECONNECTING
                    await self._handle_disconnection()
                    raise ConnectionClosedException(f"WebSocket closed by server (code: {self._ws.close_code}).")
                else: # Other types (BINARY, PING, PONG, etc.) - log and ignore or handle as needed
                    logger.debug(f"Received non-text WebSocket message type: {websocket_message.type}")
                    # Continue receiving the next message in the loop
                    # Need to return something or loop here - this simple return breaks iteration
                    # Better: loop within recv until a TEXT message or error/close occurs
                    # For simplicity now, we'll let __anext__ call recv again
                    # A robust implementation might use a queue filled by a background receive task
                    raise ConnectionError(f"Unsupported WebSocket message type received: {websocket_message.type}") # Temporary: Fail on unexpected types

            except (ConnectionResetError) as e:
                logger.error(f"Receive failed due to connection error: {e}. State: {self._state.name}. Attempting reconnect.", exc_info=True)
                self._state = ClientState.RECONNECTING
                await self._handle_disconnection()
                # After handling, raise to signal the iterator to stop or retry
                raise ConnectionClosedException("Connection lost during receive.") from e
            except asyncio.TimeoutError:
                 logger.warning("Timeout waiting for message.")
                 # Maybe just return None or raise specific timeout error?
                 # For now, let it propagate if not handled by a wrapper
                 raise
        else:
             # This case should ideally be handled by the initial state check + _ensure_connected
             logger.error(f"recv called but WebSocket not connected or available in state {self._state.name}.")
             await self._handle_disconnection()
             raise ConnectionClosedException("WebSocket was not connected when recv was called.")


    async def _ensure_connected(self):
        """Blocks until connection is established or reconnection fails."""
        if self._state == ClientState.CONNECTED:
            return
        if self._state in (ClientState.IDLE, ClientState.CLOSED, ClientState.RECONNECTING):
            try:
                logger.info("Ensuring connection...")
                # `connect` is the decorated method with retries
                await self.connect()
            except Exception as e:
                logger.critical("Failed to establish or re-establish connection after retries.", exc_info=True)
                # Ensure state is CLOSED if connect fails permanently
                self._state = ClientState.CLOSED
                raise ConnectionError("Connection unavailable and reconnection failed.") from e
        elif self._state == ClientState.CONNECTING:
            # If already connecting, wait for it to resolve (needs more complex state/event)
            # Simple approach: short sleep and check again (crude)
            logger.debug("Waiting for ongoing connection attempt...")
            while self._state == ClientState.CONNECTING:
                await asyncio.sleep(0.1)
            if self._state != ClientState.CONNECTED:
                 raise ConnectionError(f"Connection attempt finished in non-connected state: {self._state.name}")


    async def _handle_disconnection(self):
        """Attempts to reconnect after a detected disconnection."""
        logger.warning(f"Handling disconnection detected in state: {self._state.name}")
        # Clean up the old socket
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        # Set state to RECONNECTING if not already set
        if self._state != ClientState.RECONNECTING:
            self._state = ClientState.RECONNECTING

        try:
            await self._ensure_connected() # Try reconnecting (uses decorated connect)
            logger.info("Reconnection successful.")
        except ConnectionError:
            # Reconnection failed after retries
            logger.error("Reconnection failed.")
            # State should already be CLOSED from _ensure_connected failure path
            # Propagate the failure
            raise


    def __aiter__(self) -> AsyncIterator[ServerMessageType]:
        return self

    async def __anext__(self) -> ServerMessageType:
        try:
            # Rely on recv to handle state, connection, and return/raise appropriately
            message = await self.recv()
            return message
        except ConnectionClosedException as e:
            # Stop iteration cleanly on expected close or unrecoverable connection failure
            logger.info(f"Stopping async iteration due to connection closure: {e}")
            raise StopAsyncIteration from e
        except Exception:
             # Log unexpected errors during iteration but still stop
             logger.exception("Unexpected error during async iteration.")
             raise StopAsyncIteration


    async def close(self):
        logger.info(f"Close called. Current state: {self._state.name} -> CLOSING")
        if self._state == ClientState.CLOSED:
             logger.info("Already closed.")
             return

        self._state = ClientState.CLOSING
        # Close WebSocket if it exists and isn't already closed
        if self._ws and not self._ws.closed:
            await self._ws.close()
            logger.debug("WebSocket closed.")
        self._ws = None

        # Close the session ONLY if this class instance created it
        if self._session and not self._session.closed and self._manage_session:
            await self._session.close()
            logger.debug("Owned ClientSession closed.")
        self._session = None # Release reference

        self._state = ClientState.CLOSED
        logger.info(f"Client closed. Final state: {self._state.name}")


    @property
    def closed(self) -> bool:
        # Check state rather than just ws object, accounts for failed connections
        return self._state == ClientState.CLOSED

    @property
    def current_state(self) -> ClientState:
        return self._state


    async def __aenter__(self):
        # Connect is decorated, will retry
        await self.connect()
        # Ensure connect succeeded, otherwise __aenter__ raises exception
        if self._state != ClientState.CONNECTED:
             raise ConnectionError(f"Failed to connect within __aenter__ final state: {self._state.name}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()