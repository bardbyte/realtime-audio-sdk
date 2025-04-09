# import asyncio
# import base64
# import os
# import sys

# import numpy as np
# import soundfile as sf
# from azure.core.credentials import AzureKeyCredential
# from dotenv import load_dotenv
# from scipy.signal import resample

# from rtclient import (
#     InputAudioBufferAppendMessage,
#     InputAudioTranscription,
#     RTLowLevelClient,
#     ServerVAD,
#     SessionUpdateMessage,
#     SessionUpdateParams,
# )


# def resample_audio(audio_data, original_sample_rate, target_sample_rate):
#     number_of_samples = round(len(audio_data) * float(target_sample_rate) / original_sample_rate)
#     resampled_audio = resample(audio_data, number_of_samples)
#     return resampled_audio.astype(np.int16)


# async def send_audio(client: RTLowLevelClient, audio_file_path: str):
#     sample_rate = 24000
#     duration_ms = 100
#     samples_per_chunk = sample_rate * (duration_ms / 1000)
#     bytes_per_sample = 2
#     bytes_per_chunk = int(samples_per_chunk * bytes_per_sample)

#     extra_params = (
#         {
#             "samplerate": sample_rate,
#             "channels": 1,
#             "subtype": "PCM_16",
#         }
#         if audio_file_path.endswith(".raw")
#         else {}
#     )

#     audio_data, original_sample_rate = sf.read(audio_file_path, dtype="int16", **extra_params)

#     if original_sample_rate != sample_rate:
#         audio_data = resample_audio(audio_data, original_sample_rate, sample_rate)

#     audio_bytes = audio_data.tobytes()

#     for i in range(0, len(audio_bytes), bytes_per_chunk):
#         chunk = audio_bytes[i : i + bytes_per_chunk]
#         base64_audio = base64.b64encode(chunk).decode("utf-8")
#         await client.send(InputAudioBufferAppendMessage(audio=base64_audio))


# async def receive_messages(client: RTLowLevelClient):
#     while not client.closed:
#         message = await client.recv()
#         if message is None:
#             continue
#         match message.type:
#             case "session.created":
#                 print("Session Created Message")
#                 print(f"  Model: {message.session.model}")
#                 print(f"  Session Id: {message.session.id}")
#                 pass
#             case "error":
#                 print("Error Message")
#                 print(f"  Error: {message.error}")
#                 pass
#             case "input_audio_buffer.committed":
#                 print("Input Audio Buffer Committed Message")
#                 print(f"  Item Id: {message.item_id}")
#                 pass
#             case "input_audio_buffer.cleared":
#                 print("Input Audio Buffer Cleared Message")
#                 pass
#             case "input_audio_buffer.speech_started":
#                 print("Input Audio Buffer Speech Started Message")
#                 print(f"  Item Id: {message.item_id}")
#                 print(f"  Audio Start [ms]: {message.audio_start_ms}")
#                 pass
#             case "input_audio_buffer.speech_stopped":
#                 print("Input Audio Buffer Speech Stopped Message")
#                 print(f"  Item Id: {message.item_id}")
#                 print(f"  Audio End [ms]: {message.audio_end_ms}")
#                 pass
#             case "conversation.item.created":
#                 print("Conversation Item Created Message")
#                 print(f"  Id: {message.item.id}")
#                 print(f"  Previous Id: {message.previous_item_id}")
#                 if message.item.type == "message":
#                     print(f"  Role: {message.item.role}")
#                     for index, content in enumerate(message.item.content):
#                         print(f"  [{index}]:")
#                         print(f"    Content Type: {content.type}")
#                         if content.type == "input_text" or content.type == "text":
#                             print(f"  Text: {content.text}")
#                         elif content.type == "input_audio" or content.type == "audio":
#                             print(f"  Audio Transcript: {content.transcript}")
#                 pass
#             case "conversation.item.truncated":
#                 print("Conversation Item Truncated Message")
#                 print(f"  Id: {message.item_id}")
#                 print(f" Content Index: {message.content_index}")
#                 print(f"  Audio End [ms]: {message.audio_end_ms}")
#             case "conversation.item.deleted":
#                 print("Conversation Item Deleted Message")
#                 print(f"  Id: {message.item_id}")
#             case "conversation.item.input_audio_transcription.completed":
#                 print("Input Audio Transcription Completed Message")
#                 print(f"  Id: {message.item_id}")
#                 print(f"  Content Index: {message.content_index}")
#                 print(f"  Transcript: {message.transcript}")
#             case "conversation.item.input_audio_transcription.failed":
#                 print("Input Audio Transcription Failed Message")
#                 print(f"  Id: {message.item_id}")
#                 print(f"  Error: {message.error}")
#             case "response.created":
#                 print("Response Created Message")
#                 print(f"  Response Id: {message.response.id}")
#                 print("  Output Items:")
#                 for index, item in enumerate(message.response.output):
#                     print(f"  [{index}]:")
#                     print(f"    Item Id: {item.id}")
#                     print(f"    Type: {item.type}")
#                     if item.type == "message":
#                         print(f"    Role: {item.role}")
#                         match item.role:
#                             case "system":
#                                 for content_index, content in enumerate(item.content):
#                                     print(f"    [{content_index}]:")
#                                     print(f"      Content Type: {content.type}")
#                                     print(f"      Text: {content.text}")
#                             case "user":
#                                 for content_index, content in enumerate(item.content):
#                                     print(f"    [{content_index}]:")
#                                     print(f"      Content Type: {content.type}")
#                                     if content.type == "input_text":
#                                         print(f"      Text: {content.text}")
#                                     elif content.type == "input_audio":
#                                         print(f"      Audio Data Length: {len(content.audio)}")
#                             case "assistant":
#                                 for content_index, content in enumerate(item.content):
#                                     print(f"    [{content_index}]:")
#                                     print(f"      Content Type: {content.type}")
#                                     print(f"      Text: {content.text}")
#                     elif item.type == "function_call":
#                         print(f"    Call Id: {item.call_id}")
#                         print(f"    Function Name: {item.name}")
#                         print(f"    Parameters: {item.arguments}")
#                     elif item.type == "function_call_output":
#                         print(f"    Call Id: {item.call_id}")
#                         print(f"    Output: {item.output}")
#             case "response.done":
#                 print("Response Done Message")
#                 print(f"  Response Id: {message.response.id}")
#                 if message.response.status_details:
#                     print(f"  Status Details: {message.response.status_details.model_dump_json()}")
#                 break
#             case "response.output_item.added":
#                 print("Response Output Item Added Message")
#                 print(f"  Response Id: {message.response_id}")
#                 print(f"  Item Id: {message.item.id}")
#             case "response.output_item.done":
#                 print("Response Output Item Done Message")
#                 print(f"  Response Id: {message.response_id}")
#                 print(f"  Item Id: {message.item.id}")

#             case "response.content_part.added":
#                 print("Response Content Part Added Message")
#                 print(f"  Response Id: {message.response_id}")
#                 print(f"  Item Id: {message.item_id}")
#             case "response.content_part.done":
#                 print("Response Content Part Done Message")
#                 print(f"  Response Id: {message.response_id}")
#                 print(f"  ItemPart Id: {message.item_id}")
#             case "response.text.delta":
#                 print("Response Text Delta Message")
#                 print(f"  Response Id: {message.response_id}")
#                 print(f"  Text: {message.delta}")
#             case "response.text.done":
#                 print("Response Text Done Message")
#                 print(f"  Response Id: {message.response_id}")
#                 print(f"  Text: {message.text}")
#             case "response.audio_transcript.delta":
#                 print("Response Audio Transcript Delta Message")
#                 print(f"  Response Id: {message.response_id}")
#                 print(f"  Item Id: {message.item_id}")
#                 print(f"  Transcript: {message.delta}")
#             case "response.audio_transcript.done":
#                 print("Response Audio Transcript Done Message")
#                 print(f"  Response Id: {message.response_id}")
#                 print(f"  Item Id: {message.item_id}")
#                 print(f"  Transcript: {message.transcript}")
#             case "response.audio.delta":
#                 print("Response Audio Delta Message")
#                 print(f"  Response Id: {message.response_id}")
#                 print(f"  Item Id: {message.item_id}")
#                 print(f"  Audio Data Length: {len(message.delta)}")
#             case "response.audio.done":
#                 print("Response Audio Done Message")
#                 print(f"  Response Id: {message.response_id}")
#                 print(f"  Item Id: {message.item_id}")
#             case "response.function_call_arguments.delta":
#                 print("Response Function Call Arguments Delta Message")
#                 print(f"  Response Id: {message.response_id}")
#                 print(f"  Arguments: {message.delta}")
#             case "response.function_call_arguments.done":
#                 print("Response Function Call Arguments Done Message")
#                 print(f"  Response Id: {message.response_id}")
#                 print(f"  Arguments: {message.arguments}")
#             case "rate_limits.updated":
#                 print("Rate Limits Updated Message")
#                 print(f"  Rate Limits: {message.rate_limits}")
#             case _:
#                 print("Unknown Message")


# def get_env_var(var_name: str) -> str:
#     value = os.environ.get(var_name)
#     if not value:
#         raise OSError(f"Environment variable '{var_name}' is not set or is empty.")
#     return value


# async def with_azure_openai(audio_file_path: str):
#     endpoint = get_env_var("AZURE_OPENAI_ENDPOINT")
#     key = get_env_var("AZURE_OPENAI_API_KEY")
#     deployment = get_env_var("AZURE_OPENAI_DEPLOYMENT")
#     async with RTLowLevelClient(
#         endpoint, key_credential=AzureKeyCredential(key), azure_deployment=deployment
#     ) as client:
#         await client.send(
#             SessionUpdateMessage(
#                 session=SessionUpdateParams(
#                     turn_detection=ServerVAD(type="server_vad"),
#                     input_audio_transcription=InputAudioTranscription(model="whisper-1"),
#                 )
#             )
#         )

#         await asyncio.gather(send_audio(client, audio_file_path), receive_messages(client))


# async def with_openai(audio_file_path: str):
#     key = get_env_var("OPENAI_API_KEY")
#     model = get_env_var("OPENAI_MODEL")
#     async with RTLowLevelClient(key_credential=AzureKeyCredential(key), model=model) as client:
#         await client.send(
#             SessionUpdateMessage(session=SessionUpdateParams(turn_detection=ServerVAD(type="server_vad")))
#         )

#         await asyncio.gather(send_audio(client, audio_file_path), receive_messages(client))


# if __name__ == "__main__":
#     load_dotenv()
#     if len(sys.argv) < 2:
#         print("Usage: python sample.py <audio file> <azure|openai>")
#         print("If second argument is not provided, it will default to azure")
#         sys.exit(1)

#     file_path = sys.argv[1]
#     if len(sys.argv) == 3 and sys.argv[2] == "openai":
#         asyncio.run(with_openai(file_path))
#     else:
#         asyncio.run(with_azure_openai(file_path))


# # low_level_sample.py
# import asyncio
# import base64
# import os
# import sys
# import logging # CHANGED: Added logging import

# import numpy as np
# import soundfile as sf
# from azure.core.credentials import AzureKeyCredential
# from dotenv import load_dotenv
# from scipy.signal import resample

# # CHANGED: Import necessary components from the enhanced client module
# from rtclient.low_level_client import (
#     RTLowLevelClient,
#     ConnectionError,          # Import specific exceptions
#     AuthenticationError,
#     ConnectionClosedException,
#     InvalidMessageFormatError
# )
# # Assuming these message type models are in rtclient/models.py or similar
# from rtclient.models import (
#     InputAudioBufferAppendMessage,
#     InputAudioTranscription,    # Used in with_azure_openai
#     ServerVAD,
#     SessionUpdateMessage,
#     SessionUpdateParams,
# )

# # --- Configure Logging ---
# # CHANGED: Added basic logging configuration
# logging.basicConfig(
#     level=logging.INFO, # Set to DEBUG for more verbose client logs
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__) # Get logger for the sample script


# def resample_audio(audio_data, original_sample_rate, target_sample_rate):
#     # (Keep this function as is)
#     number_of_samples = round(len(audio_data) * float(target_sample_rate) / original_sample_rate)
#     resampled_audio = resample(audio_data, number_of_samples)
#     return resampled_audio.astype(np.int16)


# async def send_audio(client: RTLowLevelClient, audio_file_path: str):
#     # (Keep this function mostly as is)
#     # It implicitly benefits from the robust client.send() method
#     logger.info(f"Starting to send audio from: {audio_file_path}")
#     sample_rate = 24000
#     duration_ms = 100
#     samples_per_chunk = sample_rate * (duration_ms / 1000)
#     bytes_per_sample = 2
#     bytes_per_chunk = int(samples_per_chunk * bytes_per_sample)

#     extra_params = ({ "samplerate": sample_rate, "channels": 1, "subtype": "PCM_16",} if audio_file_path.endswith(".raw") else {})

#     try:
#         audio_data, original_sample_rate = sf.read(audio_file_path, dtype="int16", **extra_params)
#         logger.debug(f"Read audio file, original SR: {original_sample_rate}")
#     except Exception as e:
#          logger.error(f"Failed to read audio file {audio_file_path}: {e}", exc_info=True)
#          raise # Or handle more gracefully

#     if original_sample_rate != sample_rate:
#         logger.info(f"Resampling audio from {original_sample_rate} Hz to {sample_rate} Hz")
#         audio_data = resample_audio(audio_data, original_sample_rate, sample_rate)

#     audio_bytes = audio_data.tobytes()
#     total_bytes = len(audio_bytes)
#     logger.info(f"Total audio bytes to send: {total_bytes}")

#     bytes_sent = 0
#     try:
#         for i in range(0, total_bytes, bytes_per_chunk):
#             chunk = audio_bytes[i : i + bytes_per_chunk]
#             base64_audio = base64.b64encode(chunk).decode("utf-8")
#             # The client's send method now handles potential reconnections/retries
#             await client.send(InputAudioBufferAppendMessage(audio=base64_audio))
#             bytes_sent += len(chunk)
#             # logger.debug(f"Sent audio chunk {i // bytes_per_chunk + 1}, bytes: {len(chunk)}") # Verbose logging
#         logger.info(f"Finished sending {bytes_sent} audio bytes.")
#     except ConnectionClosedException as e:
#          logger.error(f"Connection closed while sending audio: {e}")
#          # Propagate or handle as needed - often the receive loop will also detect this
#     except Exception as e:
#         logger.exception(f"An unexpected error occurred during audio sending")
#         # Propagate or handle


# # CHANGED: Rewritten receive_messages using async iterator and exception handling
# async def receive_messages(client: RTLowLevelClient):
#     logger.info("Receive loop starting...")
#     message_count = 0
#     try:
#         # Use the client as an async iterator
#         async for message in client:
#             message_count += 1
#             logger.debug(f"Received message #{message_count} (type: {message.type})")

#             # --- Process the successfully received message ---
#             # Using print statements here, but could be proper logging
#             match message.type:
#                 case "session.created":
#                     print(f"[RECV] Session Created: ID={message.session.id}, Model={message.session.model}")
#                 case "error":
#                     print(f"[RECV] Server Error: {message.error}")
#                     # Decide if this server-sent error is fatal
#                 case "input_audio_buffer.committed":
#                     print(f"[RECV] Audio Committed: ID={message.item_id}")
#                 case "input_audio_buffer.cleared":
#                     print("[RECV] Audio Cleared")
#                 case "input_audio_buffer.speech_started":
#                     print(f"[RECV] Speech Started: ID={message.item_id}, Start={message.audio_start_ms}ms")
#                 case "input_audio_buffer.speech_stopped":
#                     print(f"[RECV] Speech Stopped: ID={message.item_id}, End={message.audio_end_ms}ms")

#                 # --- Simplified Conversation/Response Items for Brevity ---
#                 case "conversation.item.created":
#                     print(f"[RECV] Conv Item Created: ID={message.item.id}")
#                     # (Add detailed printing if needed)
#                 case "conversation.item.truncated":
#                     print(f"[RECV] Conv Item Truncated: ID={message.item_id}")
#                 case "conversation.item.deleted":
#                     print(f"[RECV] Conv Item Deleted: ID={message.item_id}")
#                 case "conversation.item.input_audio_transcription.completed":
#                      print(f"[RECV] Transcription Done: ID={message.item_id}, Transcript='{message.transcript[:50]}...'")
#                 case "conversation.item.input_audio_transcription.failed":
#                      print(f"[RECV] Transcription Failed: ID={message.item_id}, Error='{message.error}'")

#                 case "response.created":
#                     print(f"[RECV] Response Created: ID={message.response.id}")
#                 case "response.done":
#                     print(f"[RECV] Response Done: ID={message.response.id}")
#                     if message.response.status_details:
#                         print(f"  Status Details: {message.response.status_details.model_dump_json()}")
#                     # No explicit break needed, StopAsyncIteration will be raised if connection closes
#                     # If you want to stop *immediately* after response.done regardless of connection state:
#                     # return # or break, depending on structure
#                 case "response.output_item.added":
#                     print(f"[RECV] Output Item Added: RespID={message.response_id}, ItemID={message.item.id}")
#                 case "response.output_item.done":
#                     print(f"[RECV] Output Item Done: RespID={message.response_id}, ItemID={message.item.id}")

#                 case "response.content_part.added":
#                      print(f"[RECV] Content Part Added: RespID={message.response_id}, ItemID={message.item_id}")
#                 case "response.content_part.done":
#                      print(f"[RECV] Content Part Done: RespID={message.response_id}, ItemID={message.item_id}")

#                 # --- Simplified Deltas ---
#                 case "response.text.delta":
#                     print(f"[RECV] Text Delta: RespID={message.response_id}, Delta='{message.delta}'")
#                 case "response.text.done":
#                      print(f"[RECV] Text Done: RespID={message.response_id}, Text='{message.text}'")
#                 # (Add other delta/done handlers as needed)

#                 case "rate_limits.updated":
#                     print(f"[RECV] Rate Limits Updated: {message.rate_limits}")
#                 case _:
#                     print(f"[RECV] Unknown Message Type: {message.type}")

#     except ConnectionClosedException as e:
#         # This exception is raised by __anext__ when the connection is lost permanently
#         logger.warning(f"Receive loop terminated: Connection closed ({e})")
#     except InvalidMessageFormatError as e:
#          # Handle badly formatted messages from server if needed
#          logger.error(f"Receive loop terminated: Invalid message format ({e})", exc_info=True)
#     except asyncio.CancelledError:
#          logger.info("Receive loop cancelled.") # Handle task cancellation
#     except Exception as e:
#         # Catch any other unexpected errors during the loop
#         logger.exception(f"An unexpected error occurred in receive loop: {e}")
#     finally:
#         logger.info(f"Receive loop finished after {message_count} messages.")


# def get_env_var(var_name: str) -> str: # Keep as is
#     value = os.environ.get(var_name)
#     if not value:
#         logger.critical(f"Environment variable '{var_name}' is not set or is empty.")
#         raise OSError(f"Environment variable '{var_name}' is not set or is empty.")
#     return value


# # CHANGED: Added top-level error handling and updated client instantiation
# async def run_azure_openai(audio_file_path: str):
#     logger.info("Configuring for Azure OpenAI...")
#     try:
#         azure_url = get_env_var("AZURE_OPENAI_ENDPOINT") # Use 'url' to match client param
#         key = get_env_var("AZURE_OPENAI_API_KEY")
#         deployment = get_env_var("AZURE_OPENAI_DEPLOYMENT")
#         # Optional: Get API version/path from env or use client defaults
#         # api_version = os.getenv("AZURE_OPENAI_API_VERSION") # Example
#         # api_path = os.getenv("AZURE_OPENAI_PATH")          # Example

#         async with RTLowLevelClient(
#             url=azure_url, # Pass the Azure base URL
#             key_credential=AzureKeyCredential(key),
#             azure_deployment=deployment
#             # Pass explicit api_version/api_path if needed, otherwise defaults are used
#             # azure_api_version=api_version if api_version else "2024-10-01-preview",
#             # azure_api_path=api_path if api_path else "/openai/realtime",
#         ) as client:
#             logger.info("Client context entered. Sending session update...")
#             # Send initial configuration message
#             await client.send(
#                 SessionUpdateMessage(
#                     session=SessionUpdateParams(
#                         turn_detection=ServerVAD(type="server_vad"),
#                         input_audio_transcription=InputAudioTranscription(model="whisper-1"), # Example setting
#                     )
#                 )
#             )
#             logger.info("Session update sent. Starting send/receive tasks...")
#             # Run send and receive concurrently
#             await asyncio.gather(
#                 send_audio(client, audio_file_path),
#                 receive_messages(client)
#             )

#     # Catch specific errors during client setup or operation
#     except (ConnectionError, AuthenticationError) as e:
#         logger.critical(f"Azure connection failed permanently: {e}", exc_info=True)
#     except OSError as e:
#          logger.critical(f"Configuration error: {e}") # Error from get_env_var
#     except Exception as e:
#         logger.exception("An unexpected error occurred during Azure OpenAI run.")


# # CHANGED: Added top-level error handling and updated client instantiation
# async def run_openai(audio_file_path: str):
#     logger.info("Configuring for OpenAI...")
#     try:
#         key = get_env_var("OPENAI_API_KEY")
#         model = get_env_var("OPENAI_MODEL") # e.g., "gpt-4o"

#         # url=None tells the client to use the default OpenAI WebSocket URL
#         async with RTLowLevelClient(
#             url=None,
#             key_credential=AzureKeyCredential(key), # Wrap OpenAI key
#             model=model
#         ) as client:
#             logger.info("Client context entered. Sending session update...")
#             # Send initial configuration message (adjust params for OpenAI if needed)
#             await client.send(
#                 SessionUpdateMessage(
#                     session=SessionUpdateParams(
#                         turn_detection=ServerVAD(type="server_vad")
#                         # Add other OpenAI specific params if available/needed
#                     )
#                 )
#             )
#             logger.info("Session update sent. Starting send/receive tasks...")
#             # Run send and receive concurrently
#             await asyncio.gather(
#                 send_audio(client, audio_file_path),
#                 receive_messages(client)
#             )

#     # Catch specific errors during client setup or operation
#     except (ConnectionError, AuthenticationError) as e:
#         logger.critical(f"OpenAI connection failed permanently: {e}", exc_info=True)
#     except OSError as e:
#          logger.critical(f"Configuration error: {e}") # Error from get_env_var
#     except Exception as e:
#         logger.exception("An unexpected error occurred during OpenAI run.")


# # CHANGED: Updated main block for clarity and consistency
# if __name__ == "__main__":
#     load_dotenv()
#     logger.info("Low Level Sample Script Started")

#     if len(sys.argv) < 2:
#         print("Usage: python low_level_sample.py <audio file> [azure|openai]")
#         print("Defaults to 'azure' if the second argument is omitted.")
#         sys.exit(1)

#     audio_file = sys.argv[1]
#     target_api = "azure" # Default
#     if len(sys.argv) >= 3 and sys.argv[2].lower() == "openai":
#         target_api = "openai"

#     logger.info(f"Target API: {target_api.upper()}")
#     logger.info(f"Audio file: {audio_file}")

#     if not os.path.exists(audio_file):
#         logger.critical(f"Audio file not found: {audio_file}")
#         sys.exit(1)

#     try:
#         if target_api == "openai":
#             asyncio.run(run_openai(audio_file))
#         else:
#             asyncio.run(run_azure_openai(audio_file))
#         logger.info("Sample Script Finished Successfully")
#     except KeyboardInterrupt:
#         logger.info("Script interrupted by user.")
#     except Exception as e:
#          logger.exception("Unhandled exception in main execution block.")
#          sys.exit(1) # Exit with error code on unhandled exception
#     finally:
#          logger.info("Low Level Sample Script Exiting.")

# low_level_sample.py (Enhanced Output)
import asyncio
import base64
import os
import sys
import logging

import numpy as np
import soundfile as sf
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
from scipy.signal import resample

# Import necessary components from the enhanced client module
from rtclient.low_level_client import (
    RTLowLevelClient,
    ConnectionError,
    AuthenticationError,
    ConnectionClosedException,
    InvalidMessageFormatError
)
# Import necessary message type models from models.py
from rtclient.models import (
    InputAudioBufferAppendMessage,
    InputAudioTranscription,
    ServerVAD,
    SessionUpdateMessage,
    SessionUpdateParams,
    # We don't strictly *need* to import server message types here
    # as the client handles parsing, but it helps with understanding.
)

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def resample_audio(audio_data, original_sample_rate, target_sample_rate):
    # (Keep this function as is)
    number_of_samples = round(len(audio_data) * float(target_sample_rate) / original_sample_rate)
    resampled_audio = resample(audio_data, number_of_samples)
    return resampled_audio.astype(np.int16)


async def send_audio(client: RTLowLevelClient, audio_file_path: str):
    # (Keep this function as is)
    logger.info(f"Starting to send audio from: {audio_file_path}")
    sample_rate = 24000
    duration_ms = 100
    samples_per_chunk = sample_rate * (duration_ms / 1000)
    bytes_per_sample = 2
    bytes_per_chunk = int(samples_per_chunk * bytes_per_sample)

    extra_params = ({ "samplerate": sample_rate, "channels": 1, "subtype": "PCM_16",} if audio_file_path.endswith(".raw") else {})

    try:
        audio_data, original_sample_rate = sf.read(audio_file_path, dtype="int16", **extra_params)
        logger.debug(f"Read audio file, original SR: {original_sample_rate}")
    except Exception as e:
         logger.error(f"Failed to read audio file {audio_file_path}: {e}", exc_info=True)
         raise

    if original_sample_rate != sample_rate:
        logger.info(f"Resampling audio from {original_sample_rate} Hz to {sample_rate} Hz")
        audio_data = resample_audio(audio_data, original_sample_rate, sample_rate)

    audio_bytes = audio_data.tobytes()
    total_bytes = len(audio_bytes)
    logger.info(f"Total audio bytes to send: {total_bytes}")

    bytes_sent = 0
    try:
        for i in range(0, total_bytes, bytes_per_chunk):
            chunk = audio_bytes[i : i + bytes_per_chunk]
            base64_audio = base64.b64encode(chunk).decode("utf-8")
            await client.send(InputAudioBufferAppendMessage(audio=base64_audio))
            bytes_sent += len(chunk)
        logger.info(f"Finished sending {bytes_sent} audio bytes.")
    except ConnectionClosedException as e:
         logger.error(f"Connection closed while sending audio: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred during audio sending")


# CHANGED: Added cases for previously unknown message types
async def receive_messages(client: RTLowLevelClient):
    logger.info("Receive loop starting...")
    message_count = 0
    try:
        async for message in client:
            message_count += 1
            logger.debug(f"Received message #{message_count} (type: {message.type})")

            match message.type:
                # --- Session Management ---
                case "session.created":
                    # Access attributes defined in SessionCreatedMessage model
                    print(f"[RECV] Session Created: ID={message.session.id}, Model={message.session.model}")
                case "session.updated": # ADDED Case
                    # Access attributes defined in SessionUpdatedMessage model
                    print(f"[RECV] Session Updated: ID={message.session.id}")
                    # You could print message.session attributes like voice, temp etc. if needed
                    # print(f"  Voice: {message.session.voice}, Temp: {message.session.temperature}")

                # --- Errors ---
                case "error":
                    # Access attributes defined in ErrorMessage model
                    print(f"[RECV] Server Error: Type={message.error.type}, Code={message.error.code}, Msg='{message.error.message}'")

                # --- Input Audio Buffer Status ---
                case "input_audio_buffer.committed":
                    print(f"[RECV] Audio Committed: ID={message.item_id}")
                case "input_audio_buffer.cleared":
                    print("[RECV] Audio Cleared")
                case "input_audio_buffer.speech_started":
                    print(f"[RECV] Speech Started: ID={message.item_id}, Start={message.audio_start_ms}ms")
                case "input_audio_buffer.speech_stopped":
                    print(f"[RECV] Speech Stopped: ID={message.item_id}, End={message.audio_end_ms}ms")

                # --- Conversation Items ---
                case "conversation.item.created":
                    # Access attributes from ItemCreatedMessage -> ResponseItem
                    print(f"[RECV] Conv Item Created: ID={message.item.id}, Type={message.item.type}, Role={getattr(message.item, 'role', 'N/A')}")
                case "conversation.item.truncated":
                    print(f"[RECV] Conv Item Truncated: ID={message.item_id}")
                case "conversation.item.deleted":
                    print(f"[RECV] Conv Item Deleted: ID={message.item_id}")

                # --- Transcription Status ---
                case "conversation.item.input_audio_transcription.completed":
                     print(f"[RECV] Input Transcription Done: ID={message.item_id}, Transcript='{message.transcript[:50]}...'")
                case "conversation.item.input_audio_transcription.failed":
                     print(f"[RECV] Input Transcription Failed: ID={message.item_id}, Error='{message.error}'")

                # --- Response Lifecycle ---
                case "response.created":
                    # Access attributes from ResponseCreatedMessage -> Response
                    print(f"[RECV] Response Created: ID={message.response.id}")
                case "response.done":
                    # Access attributes from ResponseDoneMessage -> Response
                    print(f"[RECV] Response Done: ID={message.response.id}, Status={message.response.status}")
                    if message.response.status_details:
                        print(f"  Status Details: {message.response.status_details.model_dump_json()}")
                    if message.response.usage:
                         print(f"  Usage: {message.response.usage.total_tokens} total tokens")

                # --- Response Structure ---
                case "response.output_item.added":
                    # Access attributes from ResponseOutputItemAddedMessage -> ResponseItem
                    print(f"[RECV] Output Item Added: RespID={message.response_id}, ItemID={message.item.id}, Type={message.item.type}")
                case "response.output_item.done":
                    print(f"[RECV] Output Item Done: RespID={message.response_id}, ItemID={message.item.id}")
                case "response.content_part.added":
                     # Access attributes from ResponseContentPartAddedMessage -> ResponseItemContentPart
                     print(f"[RECV] Content Part Added: RespID={message.response_id}, ItemID={message.item_id}, Type={message.part.type}")
                case "response.content_part.done":
                     print(f"[RECV] Content Part Done: RespID={message.response_id}, ItemID={message.item_id}, Type={message.part.type}")

                # --- Response Content Deltas / Done ---
                case "response.text.delta":
                    # Access attributes from ResponseTextDeltaMessage
                    print(f"[RECV] Text Delta: RespID={message.response_id}, ItemID={message.item_id}, Delta='{message.delta}'")
                case "response.text.done":
                     # Access attributes from ResponseTextDoneMessage
                     print(f"[RECV] Text Done: RespID={message.response_id}, ItemID={message.item_id}, Text='{message.text}'")

                case "response.audio_transcript.delta": # ADDED Case
                    # Access attributes from ResponseAudioTranscriptDeltaMessage
                    print(f"[RECV] Audio Transcript Delta: RespID={message.response_id}, ItemID={message.item_id}, Delta='{message.delta}'")
                case "response.audio_transcript.done": # ADDED Case
                    # Access attributes from ResponseAudioTranscriptDoneMessage
                    print(f"[RECV] Audio Transcript Done: RespID={message.response_id}, ItemID={message.item_id}, Transcript='{message.transcript}'")

                case "response.audio.delta": # ADDED Case
                    # Access attributes from ResponseAudioDeltaMessage
                    # Print length as audio data can be large
                    print(f"[RECV] Audio Delta: RespID={message.response_id}, ItemID={message.item_id}, DeltaLength={len(message.delta)}")
                case "response.audio.done": # ADDED Case
                    # Access attributes from ResponseAudioDoneMessage
                    print(f"[RECV] Audio Done: RespID={message.response_id}, ItemID={message.item_id}")

                case "response.function_call_arguments.delta":
                    # Access attributes from ResponseFunctionCallArgumentsDeltaMessage
                    print(f"[RECV] Func Args Delta: RespID={message.response_id}, ItemID={message.item_id}, Delta='{message.delta}'")
                case "response.function_call_arguments.done":
                    # Access attributes from ResponseFunctionCallArgumentsDoneMessage
                    print(f"[RECV] Func Args Done: RespID={message.response_id}, ItemID={message.item_id}, Name='{message.name}', Args='{message.arguments}'")

                # --- Rate Limits ---
                case "rate_limits.updated":
                    # Access attributes from RateLimitsUpdatedMessage -> list[RateLimits]
                    limits_str = ", ".join([f"{rl.name}={rl.remaining}/{rl.limit}" for rl in message.rate_limits])
                    print(f"[RECV] Rate Limits Updated: {limits_str}")

                # --- Default Case ---
                case _:
                    # This will now be hit less often, only for truly unexpected types
                    print(f"[RECV] *** Unknown Message Type Encountered: {message.type} ***")
                    print(f"      Data: {message}") # Print the whole message object for debugging

    except ConnectionClosedException as e:
        logger.warning(f"Receive loop terminated: Connection closed ({e})")
    except InvalidMessageFormatError as e:
         logger.error(f"Receive loop terminated: Invalid message format ({e})", exc_info=True)
    except asyncio.CancelledError:
         logger.info("Receive loop cancelled.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in receive loop: {e}")
    finally:
        logger.info(f"Receive loop finished after {message_count} messages.")


def get_env_var(var_name: str) -> str: # Keep as is
    value = os.environ.get(var_name)
    if not value:
        logger.critical(f"Environment variable '{var_name}' is not set or is empty.")
        raise OSError(f"Environment variable '{var_name}' is not set or is empty.")
    return value


async def run_azure_openai(audio_file_path: str):
    # (Keep this function as is, including error handling)
    logger.info("Configuring for Azure OpenAI...")
    try:
        azure_url = get_env_var("AZURE_OPENAI_ENDPOINT")
        key = get_env_var("AZURE_OPENAI_API_KEY")
        deployment = get_env_var("AZURE_OPENAI_DEPLOYMENT")

        async with RTLowLevelClient(
            url=azure_url,
            key_credential=AzureKeyCredential(key),
            azure_deployment=deployment
        ) as client:
            logger.info("Client context entered. Sending session update...")
            await client.send(
                SessionUpdateMessage(
                    session=SessionUpdateParams(
                        turn_detection=ServerVAD(type="server_vad"),
                        input_audio_transcription=InputAudioTranscription(model="whisper-1"),
                    )
                )
            )
            logger.info("Session update sent. Starting send/receive tasks...")
            await asyncio.gather(
                send_audio(client, audio_file_path),
                receive_messages(client)
            )
    except (ConnectionError, AuthenticationError) as e:
        logger.critical(f"Azure connection failed permanently: {e}", exc_info=True)
    except OSError as e:
         logger.critical(f"Configuration error: {e}")
    except Exception as e:
        logger.exception("An unexpected error occurred during Azure OpenAI run.")


async def run_openai(audio_file_path: str):
    # (Keep this function as is, including error handling)
    logger.info("Configuring for OpenAI...")
    try:
        key = get_env_var("OPENAI_API_KEY")
        model = get_env_var("OPENAI_MODEL")

        async with RTLowLevelClient(
            url=None,
            key_credential=AzureKeyCredential(key),
            model=model
        ) as client:
            logger.info("Client context entered. Sending session update...")
            await client.send(
                SessionUpdateMessage(
                    session=SessionUpdateParams(
                        turn_detection=ServerVAD(type="server_vad")
                    )
                )
            )
            logger.info("Session update sent. Starting send/receive tasks...")
            await asyncio.gather(
                send_audio(client, audio_file_path),
                receive_messages(client)
            )
    except (ConnectionError, AuthenticationError) as e:
        logger.critical(f"OpenAI connection failed permanently: {e}", exc_info=True)
    except OSError as e:
         logger.critical(f"Configuration error: {e}")
    except Exception as e:
        logger.exception("An unexpected error occurred during OpenAI run.")


# (Keep main execution block as is)
if __name__ == "__main__":
    load_dotenv()
    logger.info("Low Level Sample Script Started")

    if len(sys.argv) < 2:
        print("Usage: python low_level_sample.py <audio file> [azure|openai]")
        print("Defaults to 'azure' if the second argument is omitted.")
        sys.exit(1)

    audio_file = sys.argv[1]
    target_api = "azure"
    if len(sys.argv) >= 3 and sys.argv[2].lower() == "openai":
        target_api = "openai"

    logger.info(f"Target API: {target_api.upper()}")
    logger.info(f"Audio file: {audio_file}")

    if not os.path.exists(audio_file):
        logger.critical(f"Audio file not found: {audio_file}")
        sys.exit(1)

    try:
        if target_api == "openai":
            asyncio.run(run_openai(audio_file))
        else:
            asyncio.run(run_azure_openai(audio_file))
        logger.info("Sample Script Finished Successfully")
    except KeyboardInterrupt:
        logger.info("Script interrupted by user.")
    except Exception as e:
         logger.exception("Unhandled exception in main execution block.")
         sys.exit(1)
    finally:
         logger.info("Low Level Sample Script Exiting.")