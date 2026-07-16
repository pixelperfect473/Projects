import json
import os
import glob
import shutil


def convert_transcripts_to_dialogue(
    input_dir="transcribed",
    output_dir="dialogue",
    processed_dir="processed",
):

    # Make sure the output folders exist
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    # Find all JSON files in the transcript folder
    json_files = glob.glob(os.path.join(input_dir, "*.json"))

    if not json_files:
        print(f"No JSON files found in '{input_dir}'")
        return []

    results = []

    for json_path in json_files:
        # Load transcript
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        words = data.get("words", [])

        # Initialize variables
        script = []
        current_speaker = None
        current_line = []

        for w in words:
            speaker = w.get("speaker_id")
            word_type = w.get("type")
            text = w.get("text")

            # Skip spacing/audio events
            if word_type in ["spacing", "audio_event"]:
                continue

            # New speaker = saving previous line
            if speaker != current_speaker:
                if current_line:
                    # Combine words into a line
                    script.append(f"{current_speaker}: {' '.join(current_line)}")
                current_speaker = speaker
                current_line = []

            current_line.append(text)

        # Add last line
        if current_line:
            script.append(f"{current_speaker}: {' '.join(current_line)}")

        # Output as play-style text
        play_text = "\n".join(script)

        # Build output path: same base name, .txt extension, in "dialogue" folder
        base_name = os.path.splitext(os.path.basename(json_path))[0]
        output_path = os.path.join(output_dir, f"{base_name}.txt")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(play_text)

        print(f"Processed '{json_path}' -> '{output_path}'")

        # Move the source JSON into the "processed" folder
        processed_path = os.path.join(processed_dir, os.path.basename(json_path))
        shutil.move(json_path, processed_path)
        print(f"Moved '{json_path}' -> '{processed_path}'")

        results.append((json_path, output_path))

    return results


if __name__ == "__main__":
    convert_transcripts_to_dialogue()