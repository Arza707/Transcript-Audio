import os
import time
import threading
from flask import Flask, render_template, request, send_from_directory, Response, jsonify
from pydub import AudioSegment
import speech_recognition as sr
import math

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Menyimpan file yang diunggah
uploaded_files = {}  # {filename: filepath}

# Fungsi hapus file
def delete_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    uploaded_files.pop(filename, None)

@app.route("/")
def index():
    return render_template("index.html", uploaded_files=uploaded_files)

@app.route("/Transcript Audio/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/transcribe", methods=["POST"])
def transcribe_page():
    file = request.files.get("file")
    if not file or file.filename == "":
        return "File tidak ada atau nama kosong"

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)
    uploaded_files[file.filename] = filepath
    file_url = f"/Transcript Audio/uploads/{file.filename}"

    audio = AudioSegment.from_file(filepath)
    duration_sec = int(len(audio) / 1000)

    return render_template(
        "result.html",
        file_url=file_url,
        filename=file.filename,
        audio_duration=duration_sec
    )

@app.route("/stream_transcribe/<filename>")
def stream_transcribe(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        return "File tidak ditemukan"

    def generate():
        audio = AudioSegment.from_file(filepath)
        duration_ms = len(audio)
        one_minute_ms = 60 * 1000
        num_segments = math.ceil(duration_ms / one_minute_ms)
        recognizer = sr.Recognizer()
        combined_text = ""

        for i in range(num_segments):
            start_ms = i * one_minute_ms
            end_ms = min((i + 1) * one_minute_ms, duration_ms)
            segment_audio = audio[start_ms:end_ms]

            segment_wav = os.path.join(UPLOAD_FOLDER, f"{filename}_part{i}.wav")
            segment_audio.export(segment_wav, format="wav")

            with sr.AudioFile(segment_wav) as source:
                audio_data = recognizer.record(source)
                try:
                    text = recognizer.recognize_google(audio_data, language="id-ID")
                except sr.UnknownValueError:
                    text = "[Audio tidak dikenali]"
                except sr.RequestError as e:
                    text = f"[Error Google Speech Recognition: {e}]"

            os.remove(segment_wav)
            start_sec = start_ms // 1000
            end_sec = end_ms // 1000
            timestamp = f"{start_sec//60}:{start_sec%60:02d} - {end_sec//60}:{end_sec%60:02d}"
            speaker = f"Menit Ke-{i}"
            combined_text += text + " "

            yield f"data: {timestamp}|{speaker}|{text}|{combined_text.strip()}\n\n"
            time.sleep(0.3)

        # Selesai transkrip, beri tanda FINISHED
        yield f"data: FINISHED|FINISHED|FINISHED|{combined_text.strip()}\n\n"

        # Jalankan auto delete file 2 menit setelah transkrip selesai
        threading.Thread(target=lambda: (time.sleep(120), delete_file(filename)), daemon=True).start()

    return Response(generate(), mimetype="text/event-stream")

@app.route("/delete_file/<filename>", methods=["POST"])
def delete_file_route(filename):
    delete_file(filename)
    return jsonify({"status": "deleted"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
