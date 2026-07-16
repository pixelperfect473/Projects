import transcription as trans
import dialogue as dia
import ai_analyze as ai

def main():
    try:
        print("Step 1: Transcribing calls...")
        trans.transcribe_call()

        print("Step 2: Converting to dialogue...")
        dia.convert_transcripts_to_dialogue()

        print("Step 3: Running AI analysis...")
        ai.get_analysis()

        print("Pipeline complete.")

    except Exception as e:
        print(f"Processing failed: {e}")
        raise


if __name__ == "__main__":
    main()
