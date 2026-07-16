import json
from pathlib import Path
from elevenlabs import ElevenLabs
import config

# ---- Config -----------
API_KEY = config.API_KEY  # test
MODEL_ID = "scribe_v1"
NUM_SPEAKERS = 2

SCRIPT_DIR = Path(__file__).resolve().parent
CALLS_DIR = SCRIPT_DIR / "calls"
TRANSCRIBED_DIR = SCRIPT_DIR / "transcribed"
PROCESSED_DIR = SCRIPT_DIR / "processed"
# ------------


def transcribe(client: ElevenLabs, mp3_path: Path) -> dict:
    """Send an mp3 file to ElevenLabs speech-to-text and return the result dict."""
    with open(mp3_path, "rb") as audio_file:
        transcript = client.speech_to_text.convert(
            file=audio_file,
            model_id=MODEL_ID,
            diarize=True,
            num_speakers=NUM_SPEAKERS,
        )
    return transcript.dict()


def transcribe_call() -> None:
    if not CALLS_DIR.exists():
        raise FileNotFoundError(f"Calls folder not found: {CALLS_DIR}")

    TRANSCRIBED_DIR.mkdir(exist_ok=True)

    client = ElevenLabs(api_key=API_KEY)

    mp3_files = sorted(CALLS_DIR.glob("*.mp3"))
    if not mp3_files:
        print(f"No .mp3 files found in {CALLS_DIR}")
        return

    for mp3_path in mp3_files:
        base_name = mp3_path.stem  # filename without extension
        final_mp3_path = PROCESSED_DIR / f"{base_name}.mp3"
        json_path = TRANSCRIBED_DIR / f"{base_name}.json"

        print(f"Processing: {mp3_path.name}")

        try:
            # Transcribe the mp3
            transcription_dict = transcribe(client, mp3_path)

            #  Save the transcript JSON with the same base name
            with open(json_path, "w", encoding="utf-8") as out_f:
                json.dump(transcription_dict, out_f, indent=4)

            # Move the audio file into the transcribed folder
            mp3_path.rename(final_mp3_path)

            print(f"  -> Saved transcript: {json_path.name}")
            print(f"  -> Moved audio to: {final_mp3_path}")

        except Exception as e:
            print(f"  !! Failed to process {mp3_path.name}: {e}")


if __name__ == "__main__":
    transcribe_call()