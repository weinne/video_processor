import os
import time
import requests
import hashlib
from yt_dlp import YoutubeDL
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.tools.subtitles import SubtitlesClip
from moviepy.video.VideoClip import TextClip
from moviepy.editor import *
import tkinter as tk
import assemblyai as aai
from tkinter import filedialog, messagebox

API_FILE = "apis.txt"

# Funções para gerenciar APIs
def load_apis():
    print("Carregando chaves das APIs...")
    if os.path.exists(API_FILE):
        with open(API_FILE, "r") as f:
            lines = f.readlines()
            assemblyai_key = lines[0].strip() if len(lines) > 0 else ""
            huggingface_key = lines[1].strip() if len(lines) > 1 else ""
            print("Chaves das APIs carregadas.")
            return assemblyai_key, huggingface_key
    print("Chaves das APIs carregadas.")
    return "", ""

def save_apis(assemblyai_key, huggingface_key):
    print("Salvando chaves das APIs...")
    with open(API_FILE, "w") as f:
        f.write(f"{assemblyai_key}\n{huggingface_key}\n")
    print("Chaves das APIs salvas.")

# Função para gerar hash do vídeo
def generate_video_hash(video_path):
    print(f"Gerando hash para o vídeo: {video_path}")
    hasher = hashlib.md5()
    with open(video_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    print(f"Hash gerado: {hasher.hexdigest()}")
    return hasher.hexdigest()

# Função para baixar vídeo do YouTube
def download_youtube_video(video_url, status_label=None):
    print(f"Baixando vídeo do YouTube: {video_url}")
    if status_label:
        status_label.config(text="Baixando vídeo do YouTube...")
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': '%(id)s/%(id)s.%(ext)s',
        'merge_output_format': 'mp4',
    }
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(video_url, download=True)
        video_id = info_dict.get("id", None)
    if status_label:
        status_label.config(text="Download concluído.")
    print(f"Vídeo baixado: {video_id}/{video_id}.mp4")
    return f"{video_id}/{video_id}.mp4"

# Função para transcrever áudio com AssemblyAI
def transcribe_audio_with_timestamps(audio_path, assemblyai_key, status_label=None):
    print(f"Transcrevendo áudio: {audio_path}")
    if status_label:
        status_label.config(text="Transcrevendo áudio com AssemblyAI...")
    aai.settings.api_key = assemblyai_key
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_path)

    if transcript.status == aai.TranscriptStatus.error:
        if status_label:
            status_label.config(text="Erro na transcrição.")
        raise Exception(transcript.error)
    
    if status_label:
        status_label.config(text="Transcrição concluída.")
    print("Transcrição concluída.")
    # Retornar a transcrição com timestamps
    return transcript.words

# Função para salvar transcrição em um arquivo de texto
def save_transcription(transcription, file_path):
    print(f"Salvando transcrição em: {file_path}")
    with open(file_path, 'w') as f:
        for word in transcription:
            f.write(f"{word.start} --> {word.end}: {word.text}\n")
    print("Transcrição salva.")

# Função para analisar trechos de texto com Hugging Face
def analyze_text_sentiment(text, huggingface_key, status_label=None):
    print(f"Analisando sentimento do texto: {text}")
    if status_label:
        status_label.config(text="Analisando sentimento do texto com Hugging Face...")
    url = "https://api-inference.huggingface.co/models/cardiffnlp/twitter-roberta-base-sentiment"
    headers = {"Authorization": f"Bearer {huggingface_key}"}
    response = requests.post(url, headers=headers, json={"inputs": text})
    response.raise_for_status()
    if status_label:
        status_label.config(text="Análise de sentimento concluída.")
    print("Análise de sentimento concluída.")
    return response.json()

# Seleciona os melhores trechos com base em palavras-chave ou sentimento
def get_best_clips(transcription, keywords, huggingface_key, status_label=None):
    print("Selecionando os melhores trechos...")
    if status_label:
        status_label.config(text="Selecionando os melhores trechos...")
    clips = []
    for word in transcription:
        print(f"Analisando palavra: {word.text}")
        if any(keyword in word.text for keyword in keywords):
            print(f"Palavra-chave encontrada: {word.text}")
            sentiment = analyze_text_sentiment(word.text, huggingface_key)
            score = sentiment[0]['score']
            print(f"Sentimento: {sentiment}, Score: {score}")
            clips.append({"text": word.text, "start": word.start, "end": word.end, "score": score})
    
    best_clips = sorted(clips, key=lambda x: x["score"], reverse=True)[:10]
    print(f"Melhores trechos selecionados: {best_clips}")
    if status_label:
        status_label.config(text="Seleção de trechos concluída.")
    print("Seleção de trechos concluída.")
    return best_clips

# Adiciona legendas aos clipes
def add_subtitles_to_clip(clip, subtitles, output_path):
    print(f"Adicionando legendas ao clipe e salvando em: {output_path}")
    def generator(txt):
        return TextClip(txt, font="Arial", fontsize=36, color="white", bg_color="black")
    
    subtitles_clip = SubtitlesClip(subtitles, generator)
    video_with_subtitles = clip.set_duration(subtitles_clip.duration).set_subclip(0, subtitles_clip.duration)
    final = CompositeVideoClip([clip, subtitles_clip])
    final.write_videofile(output_path, codec="libx264", audio_codec="aac")
    print("Legendas adicionadas e vídeo salvo.")

# Função para cortar e criar vários vídeos pequenos
def create_highlight_videos(video_path, best_clips, output_dir, max_duration=120):
    print(f"Criando vídeos de destaques para: {video_path}")
    video = VideoFileClip(video_path)
    current_duration = 0
    current_clips = []
    video_index = 1

    for clip in best_clips:
        print(f"Processando clipe: {clip}")
        clip_duration = (clip["end"] - clip["start"]) / 1000
        print(f"Duração do clipe: {clip_duration} segundos")
        if current_duration + clip_duration > max_duration:
            if current_clips:
                print(f"Criando vídeo de destaque {video_index} com duração {current_duration} segundos")
                final_clip = concatenate_videoclips(current_clips)
                final_clip.write_videofile(os.path.join(output_dir, f"highlight_{video_index}.mp4"), codec="libx264", audio_codec="aac")
                video_index += 1
                current_duration = 0
                current_clips = []
        
        current_clips.append(video.subclip(clip["start"] / 1000, clip["end"] / 1000))
        current_duration += clip_duration

    if current_clips:
        print(f"Criando vídeo de destaque {video_index} com duração {current_duration} segundos")
        final_clip = concatenate_videoclips(current_clips)
        final_clip.write_videofile(os.path.join(output_dir, f"highlight_{video_index}.mp4"), codec="libx264", audio_codec="aac")
    print("Vídeos de destaques criados.")

# Função principal
def process_video(video_url, keywords, assemblyai_key, huggingface_key):
    print("Iniciando processamento do vídeo...")
    print("Baixando vídeo...")
    video_path = download_youtube_video(video_url)
    
    video_id = os.path.basename(os.path.dirname(video_path))
    video_output_dir = video_id
    os.makedirs(video_output_dir, exist_ok=True)
    transcription_output_path = os.path.join(video_output_dir, f"{video_id}.txt")

    if os.path.exists(transcription_output_path):
        print("Transcrição já existe. Carregando do arquivo...")
        with open(transcription_output_path, 'r') as f:
            transcription = []
            for line in f:
                parts = line.strip().split(": ", 2)
                if len(parts) == 3:
                    start, end = parts[0].split(" --> ")
                    text = parts[2]
                    transcription.append({"start": int(start), "end": int(end), "text": text})
    else:
        print("Transcrevendo áudio...")
        transcription = transcribe_audio_with_timestamps(video_path, assemblyai_key)
        save_transcription(transcription, transcription_output_path)
        print("Transcrição concluída.")

    print("Selecionando os melhores trechos...")
    best_clips_path = os.path.join(video_output_dir, f"{video_id}_best_clips.txt")
    if os.path.exists(best_clips_path):
        print("Melhores trechos já existem. Carregando do arquivo...")
        with open(best_clips_path, 'r') as f:
            best_clips = []
            for line in f:
                parts = line.strip().split(", ")
                if len(parts) == 4:
                    best_clips.append({
                        "text": parts[0],
                        "start": int(parts[1]),
                        "end": int(parts[2]),
                        "score": float(parts[3])
                    })
    else:
        best_clips = get_best_clips(transcription, keywords, huggingface_key)
        with open(best_clips_path, 'w') as f:
            for clip in best_clips:
                f.write(f"{clip['text']}, {clip['start']}, {clip['end']}, {clip['score']}\n")
        print("Seleção de trechos concluída. Tipo de best_clips: {type(best_clips)}")
        print("Conteúdo de best_clips: {best_clips}")

    print("Criando vídeos de destaques...")
    create_highlight_videos(video_path, best_clips, video_output_dir)
    print("Vídeos de destaques criados.")

# Interface gráfica
def run_gui():
    def process():
        print("Iniciando GUI...")
        video_url = video_url_entry.get()
        keywords = keywords_entry.get().split(",") if keywords_entry.get() else None
        assemblyai_key = assemblyai_entry.get()
        huggingface_key = huggingface_entry.get()
        
        save_apis(assemblyai_key, huggingface_key)
        try:
            process_video(video_url, keywords, assemblyai_key, huggingface_key)
            messagebox.showinfo("Concluído", "Processamento finalizado!")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    root = tk.Tk()
    root.title("Processador de Vídeo")

    assemblyai_key, huggingface_key = load_apis()

    tk.Label(root, text="URL do Vídeo:").grid(row=0, column=0)
    video_url_entry = tk.Entry(root, width=50)
    video_url_entry.grid(row=0, column=1)

    tk.Label(root, text="Palavras-chave (separadas por vírgula):").grid(row=1, column=0)
    keywords_entry = tk.Entry(root, width=50)
    keywords_entry.grid(row=1, column=1)

    tk.Label(root, text="Chave da API AssemblyAI:").grid(row=2, column=0)
    assemblyai_entry = tk.Entry(root, width=50)
    assemblyai_entry.grid(row=2, column=1)
    assemblyai_entry.insert(0, assemblyai_key)

    tk.Label(root, text="Chave da API Hugging Face:").grid(row=3, column=0)
    huggingface_entry = tk.Entry(root, width=50)
    huggingface_entry.grid(row=3, column=1)
    huggingface_entry.insert(0, huggingface_key)

    process_button = tk.Button(root, text="Processar", command=process)
    process_button.grid(row=4, column=0, columnspan=2)

    root.mainloop()

if __name__ == "__main__":
    run_gui()
