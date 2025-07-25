import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from mutagen.mp3 import MP3
import pygame
import numpy as np
import threading
import fitz  # PyMuPDF for PDF support

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=256)

class MusicPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("Music Player")
        self.root.geometry("1000x600")
        self.dark_mode = False

        self.current_file = None
        self.total_length = 0
        self.start_time = 0
        self.pause_offset = 0
        self.is_paused = False
        self.is_playing = False
        self.seeking = False
        self.repeat = False

        # BPM & Metronome
        self.bpm = 120
        self.beat_interval = 60 / self.bpm
        self.metronome_running = False
        self.tick_sound = self.generate_tone(440)
        self.tock_sound = self.generate_tone(660)

        self.pdf_doc = None
        self.pdf_page_index = 0

        # Layout
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill="both", expand=True)
        self.left_frame = tk.Frame(self.main_frame)
        self.left_frame.pack(side="left", fill="y", padx=10, pady=10)
        self.right_frame = tk.Frame(self.main_frame)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        label_font = ("Arial", 9)
        button_font = ("Arial", 8)

        self.label = tk.Label(self.left_frame, text="Upload a music file", font=label_font, wraplength=180, justify="center")
        self.label.pack(pady=5)

        self.upload_btn = tk.Button(self.left_frame, text="🎵 Upload Music", command=self.load_music, width=20, font=button_font)
        self.upload_btn.pack(pady=3)

        play_stop_frame = tk.Frame(self.left_frame)
        play_stop_frame.pack(pady=3)
        self.play_btn = tk.Button(play_stop_frame, text="▶ Play", command=self.toggle_play_pause, width=9, state=tk.DISABLED, font=button_font)
        self.play_btn.pack(side="left", padx=2)
        self.stop_btn = tk.Button(play_stop_frame, text="⏹ Stop", command=self.stop_music, width=9, state=tk.DISABLED, font=button_font)
        self.stop_btn.pack(side="left", padx=2)

        button_row = tk.Frame(self.left_frame)
        button_row.pack(pady=3)
        self.restart_btn = tk.Button(button_row, text="⏮ Restart", command=self.restart_music, width=9, state=tk.DISABLED, font=button_font)
        self.restart_btn.pack(side="left", padx=2)
        self.repeat_btn = tk.Button(button_row, text="Repeat", command=self.toggle_repeat, width=9, font=button_font)
        self.repeat_btn.pack(side="left", padx=2)

        self.metronome_btn = tk.Button(self.left_frame, text="Metronome: Off", command=self.toggle_metronome, width=20, font=button_font)
        self.metronome_btn.pack(pady=3)

        bpm_frame = tk.Frame(self.left_frame)
        bpm_frame.pack(pady=5)
        bpm_label = tk.Label(bpm_frame, text="Metronome BPM:", font=button_font)
        bpm_label.pack(side="left", padx=(0,5))
        self.bpm_slider = tk.Scale(bpm_frame, from_=30, to=240, orient="horizontal", length=150, command=self.change_bpm)
        self.bpm_slider.set(self.bpm)
        self.bpm_slider.pack(side="left")

        slider_theme_frame = tk.Frame(self.right_frame)
        slider_theme_frame.pack(pady=5, anchor="w")
        self.slider = tk.Scale(slider_theme_frame, from_=0, to=100, orient="horizontal", length=400)
        self.slider.pack(side="left", padx=10)
        self.slider.bind("<Button-1>", self.slider_click)
        self.theme_btn = tk.Button(slider_theme_frame, text="🌓", command=self.toggle_theme, width=2)
        self.theme_btn.pack(side="left")

        self.time_frame = tk.Frame(self.right_frame)
        self.time_frame.pack(pady=5, anchor="w")
        self.current_time_label = tk.Label(self.time_frame, text="0:00")
        self.current_time_label.pack(side="left", padx=10)
        self.total_time_label = tk.Label(self.time_frame, text="0:00")
        self.total_time_label.pack(side="left", padx=10)

        self.upload_image_btn = tk.Button(self.right_frame, text="🖼 Upload Sheet Music", command=self.upload_sheet)
        self.upload_image_btn.pack(pady=5, anchor="w")

        self.image_frame = tk.Frame(self.right_frame)
        self.image_frame.pack(pady=10, anchor="w")

        self.image_label = tk.Label(self.image_frame)
        self.image_label.pack(side="left")

        self.pdf_nav = tk.Frame(self.image_frame)
        self.pdf_nav.pack(side="left", padx=10, fill="y")

        self.prev_btn = tk.Button(self.pdf_nav, text="←", command=self.prev_pdf_page, width=3)
        self.prev_btn.pack(pady=5)

        self.next_btn = tk.Button(self.pdf_nav, text="→", command=self.next_pdf_page, width=3)
        self.next_btn.pack(pady=5)

        self.prev_btn.config(state=tk.DISABLED)
        self.next_btn.config(state=tk.DISABLED)

        self.root.bind("<Left>", lambda event: self.prev_pdf_page())
        self.root.bind("<Right>", lambda event: self.next_pdf_page())
        self.root.bind("<space>", lambda event: self.toggle_play_pause())

        self.set_theme()
        self.update_loop()

    def generate_tone(self, frequency, duration=0.1, volume=0.5):
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        waveform = (volume * np.sin(2 * np.pi * frequency * t)).astype(np.float32)
        stereo_waveform = np.column_stack((waveform, waveform))
        return pygame.sndarray.make_sound((stereo_waveform * 32767).astype(np.int16))

    def upload_sheet(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image or PDF", "*.png *.jpg *.jpeg *.bmp *.pdf")])
        if not file_path:
            return
        if file_path.endswith(".pdf"):
            try:
                self.pdf_doc = fitz.open(file_path)
                self.pdf_page_index = 0
                self.show_pdf_page()
                self.prev_btn.config(state=tk.NORMAL)
                self.next_btn.config(state=tk.NORMAL)
            except Exception as e:
                messagebox.showerror("PDF Error", str(e))
        else:
            self.display_image(file_path)
            self.pdf_doc = None
            self.prev_btn.config(state=tk.DISABLED)
            self.next_btn.config(state=tk.DISABLED)

    def show_pdf_page(self):
        if not self.pdf_doc:
            return
        page = self.pdf_doc.load_page(self.pdf_page_index)
        zoom = 2.5  # Render at double resolution
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.thumbnail((850, 700), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self.image_label.config(image=photo)
        self.image_label.image = photo


    def prev_pdf_page(self):
        if self.pdf_doc and self.pdf_page_index > 0:
            self.pdf_page_index -= 1
            self.show_pdf_page()

    def next_pdf_page(self):
        if self.pdf_doc and self.pdf_page_index < len(self.pdf_doc) - 1:
            self.pdf_page_index += 1
            self.show_pdf_page()
    def start_metronome(self):
        """Start the metronome in a separate thread."""
        def metronome_loop():
            beat_count = 0
            while self.metronome_running and self.is_playing:
                if beat_count % 4 == 0:
                    self.tock_sound.play()  # Downbeat sound
                else:
                    self.tick_sound.play()  # Regular beat
                time.sleep(self.beat_interval)
                beat_count += 1

        self.metronome_running = True
        threading.Thread(target=metronome_loop, daemon=True).start()

    def stop_metronome(self):
        self.metronome_running = False

    def change_bpm(self, val):
        try:
            bpm = int(val)
            self.bpm = bpm
            self.beat_interval = 60 / bpm
        except Exception:
            pass  # ignore invalid input

    def set_theme(self):
        bg = "#eae8e8" if not self.dark_mode else "#121212"
        fg = "black" if not self.dark_mode else "white"
        btn_bg = "#ffffff" if not self.dark_mode else "#000000"

        self.root.configure(bg=bg)

        def style_widget(widget):
            if isinstance(widget, (tk.Label, tk.Scale)):
                widget.configure(bg=bg, fg=fg)
            elif isinstance(widget, tk.Button):
                widget.configure(bg=btn_bg, fg=fg,
                                 activebackground="#bbb" if not self.dark_mode else "#555",
                                 activeforeground=fg, highlightbackground=bg,
                                 bd=0, relief="flat")
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=bg)
                for child in widget.winfo_children():
                    style_widget(child)

        for widget in self.root.winfo_children():
            style_widget(widget)

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.set_theme()

    def upload_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")])
        if file_path:
            self.display_image(file_path)

    def display_image(self, path):
        try:
            img = Image.open(path)
            img.thumbnail((850, 700), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.image_label.configure(image=photo)
            self.image_label.image = photo
        except Exception as e:
            messagebox.showerror("Image Error", str(e))

    def load_music(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav")])
        if file_path:
            self._load_audio(file_path)

    def _load_audio(self, file_path):
        try:
            pygame.mixer.music.load(file_path)
            self.current_file = file_path

            if file_path.endswith(".mp3"):
                audio = MP3(file_path)
                self.total_length = int(audio.info.length)
            else:
                self.total_length = int(pygame.mixer.Sound(file_path).get_length())

            self.label.config(text=os.path.basename(file_path))
            self.total_time_label.config(text=self.format_time(self.total_length))
            self.slider.config(to=self.total_length)

            self.play_btn.config(state=tk.NORMAL, text="▶ Play")
            self.stop_btn.config(state=tk.NORMAL)
            self.restart_btn.config(state=tk.NORMAL)
            self.slider.set(0)
            self.is_paused = False
            self.is_playing = False
            self.pause_offset = 0
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def toggle_play_pause(self):
        if not self.current_file:
            return

        if not self.is_playing:
            if self.is_paused:
                pygame.mixer.music.unpause()
                self.start_time = time.time() - self.pause_offset
            else:
                pygame.mixer.music.play(start=self.pause_offset)
                self.start_time = time.time() - self.pause_offset
            self.play_btn.config(text="⏸ Pause")
            self.is_playing = True
            self.is_paused = False
            if self.metronome_running:
                self.start_metronome()
        else:
            pygame.mixer.music.pause()
            self.pause_offset = time.time() - self.start_time
            self.play_btn.config(text="▶ Play")
            self.is_playing = False
            self.is_paused = True
            self.stop_metronome()

    def stop_music(self):
        if self.current_file:
            pygame.mixer.music.stop()
            self.current_file = None
            self.label.config(text="No file loaded")
            self.play_btn.config(state=tk.DISABLED, text="▶ Play")
            self.stop_btn.config(state=tk.DISABLED)
            self.restart_btn.config(state=tk.DISABLED)
            self.slider.set(0)
            self.current_time_label.config(text="0:00")
            self.total_time_label.config(text="0:00")
            self.is_playing = False
            self.is_paused = False
            self.pause_offset = 0
            self.repeat = False
            self.repeat_btn.config(text="Repeat")
            self.stop_metronome()

    def restart_music(self):
        if self.current_file:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(self.current_file)
            pygame.mixer.music.play(start=0)
            self.start_time = time.time()
            self.pause_offset = 0
            self.slider.set(0)
            self.current_time_label.config(text="0:00")
            self.is_playing = True
            self.is_paused = False
            self.play_btn.config(text="⏸ Pause")
            if self.metronome_running:
                self.start_metronome()

    def toggle_repeat(self):
        self.repeat = not self.repeat
        self.repeat_btn.config(text="🔁 Repeat" if self.repeat else "Repeat")

    def toggle_metronome(self):
        if self.metronome_running:
            self.stop_metronome()
            self.metronome_btn.config(text="Metronome: Off")
        else:
            self.metronome_btn.config(text="Metronome: On")
            self.metronome_running = True
            if self.is_playing:
                self.start_metronome()

    def slider_click(self, event):
        if not self.current_file:
            return

        self.seeking = True
        x = event.x
        total = self.slider["to"]
        new_val = int((x / self.slider.winfo_width()) * total)
        self.slider.set(new_val)

        pygame.mixer.music.stop()
        pygame.mixer.music.load(self.current_file)
        pygame.mixer.music.play(start=new_val)

        self.start_time = time.time() - new_val
        self.pause_offset = new_val
        self.is_playing = True
        self.is_paused = False
        self.play_btn.config(text="⏸ Pause")

        if self.metronome_running:
            self.start_metronome()

        self.root.after(200, lambda: setattr(self, 'seeking', False))

    def update_loop(self):
        if self.is_playing and not self.seeking:
            current_pos = int(time.time() - self.start_time)
            if current_pos <= self.total_length:
                self.slider.set(current_pos)
                self.current_time_label.config(text=self.format_time(current_pos))
            else:
                if self.repeat:
                    self.restart_music()
                else:
                    self.stop_music()
        self.root.after(500, self.update_loop)

    def format_time(self, seconds):
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"


if __name__ == "__main__":
    root = tk.Tk()
    app = MusicPlayer(root)
    root.mainloop()
