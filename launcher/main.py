import customtkinter as ctk
import re
import subprocess
import os
import threading
import urllib.request
import zipfile
import tempfile
import shutil

# ==== НАСТРОЙКИ ПУТЕЙ ====
BASE_DIR = r"C:\loomlet"
GRADLE_DIR = os.path.join(BASE_DIR, "files-gradle")
BUILD_GRADLE_PATH = os.path.join(GRADLE_DIR, "build.gradle")
MODS_DIR = os.path.join(GRADLE_DIR, "run", "mods")
LOG_FILE = os.path.join(GRADLE_DIR, "run", "logs", "latest.log")

LAUNCHER_DIR = os.path.dirname(os.path.abspath(__file__))
FIRST_RUN_MARKER = os.path.join(LAUNCHER_DIR, "hello!")

REPO_ZIP_URL = "https://github.com/Kirill638849776/loomlet-launcher/archive/refs/heads/main.zip"
REPO_NAME = "loomlet-launcher-main"
REPO_SUBFOLDER = "files-gradle"

# ==== НАСТРОЙКА ВНЕШНЕГО ВИДА ====
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ================== ПРОВЕРКА JAVA ==================

def find_java_home():
    java_home = os.environ.get("JAVA_HOME", "")
    if java_home and os.path.exists(os.path.join(java_home, "bin", "java.exe")):
        return java_home

    possible_paths = [
        r"C:\Program Files\Microsoft\jdk-25.0.0.36-hotspot",
        r"C:\Program Files\Microsoft\jdk-25.0.1.8-hotspot",
        r"C:\Program Files\Microsoft\jdk-25.0.2.10-hotspot",
        r"C:\Program Files\Microsoft\jdk-25.0.3.9-hotspot",
        r"C:\Program Files\Microsoft\jdk-25.0.4.7-hotspot",
        r"C:\Program Files\Microsoft\jdk-25.0.5.21-hotspot",
    ]
    for path in possible_paths:
        if os.path.exists(os.path.join(path, "bin", "java.exe")):
            return path

    ms_dir = r"C:\Program Files\Microsoft"
    if os.path.exists(ms_dir):
        for item in os.listdir(ms_dir):
            if item.startswith("jdk-25"):
                full = os.path.join(ms_dir, item)
                if os.path.exists(os.path.join(full, "bin", "java.exe")):
                    return full

    return None


def install_jdk25(status_callback=None):
    if status_callback:
        status_callback("Установка JDK 25 через winget...")

    try:
        result = subprocess.run(
            [
                "winget", "install", "--id", "Microsoft.OpenJDK.25",
                "--exact", "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements"
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=True,
            timeout=600
        )

        if result.returncode == 0:
            if status_callback:
                status_callback("JDK 25 успешно установлен")
            return True
        else:
            if status_callback:
                status_callback(f"Ошибка установки: {result.stderr[:200]}", error=True)
            return False

    except Exception as e:
        if status_callback:
            status_callback(f"Исключение при установке: {e}", error=True)
        return False


# ================== ЛОГИКА ФАЙЛОВ ==================

def download_gradle_files(status_callback=None, progress_callback=None):
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "repo.zip")
    try:
        if status_callback:
            status_callback("Скачивание файлов Gradle с GitHub...")

        def reporthook(blocknum, blocksize, totalsize):
            if totalsize > 0 and progress_callback:
                percent = min(100, int(blocknum * blocksize * 100 / totalsize))
                progress_callback(percent)

        urllib.request.urlretrieve(REPO_ZIP_URL, zip_path, reporthook)

        if status_callback:
            status_callback("Распаковка архива...")

        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(temp_dir)

        extracted_folder = os.path.join(temp_dir, REPO_NAME, REPO_SUBFOLDER)
        if not os.path.exists(extracted_folder):
            raise Exception(f"В архиве не найдена папка {REPO_SUBFOLDER}")

        if os.path.exists(GRADLE_DIR):
            shutil.rmtree(GRADLE_DIR)
        shutil.copytree(extracted_folder, GRADLE_DIR)

        if status_callback:
            status_callback("Файлы Gradle загружены")
        return True
    except Exception as e:
        if status_callback:
            status_callback(f"Ошибка загрузки: {e}", error=True)
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def clean_gradle_cache(status_callback=None):
    gradlew = os.path.join(GRADLE_DIR, "gradlew.bat")

    if os.path.exists(gradlew):
        try:
            subprocess.run(
                [gradlew, "--stop"],
                cwd=GRADLE_DIR,
                shell=True,
                capture_output=True,
                timeout=30
            )
        except Exception:
            pass

    for folder in [".gradle", "build"]:
        path = os.path.join(GRADLE_DIR, folder)
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
            except Exception:
                pass

    if status_callback:
        status_callback("Кэш Gradle очищен")


def set_username_in_build_gradle(new_nick: str):
    with open(BUILD_GRADLE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    def remove_loom_runs_client(text):
        result = []
        i = 0
        n = len(text)
        while i < n:
            if text.startswith("loom", i):
                before_ok = (i == 0 or not text[i-1].isalnum() and text[i-1] != '_')
                after_ok = (i + 4 >= n or not text[i+4].isalnum() and text[i+4] != '_')
                if before_ok and after_ok:
                    j = i + 4
                    while j < n and text[j].isspace():
                        j += 1
                    if j < n and text[j] == '{':
                        brace_count = 1
                        k = j + 1
                        while k < n and brace_count > 0:
                            if text[k] == '{':
                                brace_count += 1
                            elif text[k] == '}':
                                brace_count -= 1
                            k += 1
                        block = text[i:k]
                        if re.search(r'\bruns\s*\{', block) and re.search(r'\bclient\s*\{', block):
                            end = k
                            while end < n and text[end] in ' \t\r\n':
                                end += 1
                            i = end
                            continue
            result.append(text[i])
            i += 1
        return ''.join(result)

    content_cleaned = remove_loom_runs_client(content)
    new_block = f'''
loom {{
    runs {{
        client {{
            programArg "--username"
            programArg "{new_nick}"
        }}
    }}
}}
'''
    final_content = content_cleaned.rstrip() + "\n" + new_block
    backup_path = BUILD_GRADLE_PATH + ".bak"
    try:
        shutil.copy(BUILD_GRADLE_PATH, backup_path)
    except Exception:
        pass
    with open(BUILD_GRADLE_PATH, "w", encoding="utf-8") as f:
        f.write(final_content)


# ================== ЭКРАН 1: ПЕРВЫЙ ЗАПУСК ==================

class FirstRunScreen(ctk.CTkFrame):
    def __init__(self, master, on_installed):
        super().__init__(master, fg_color="transparent")
        self.on_installed = on_installed

        self.inner = ctk.CTkFrame(self, fg_color="transparent")
        self.inner.place(relx=0.5, rely=0.5, anchor="center")

        self.title = ctk.CTkLabel(
            self.inner, text="ПЕРВЫЙ ЗАПУСК",
            font=ctk.CTkFont(size=36, weight="bold")
        )
        self.title.pack(pady=(0, 10))

        self.subtitle = ctk.CTkLabel(
            self.inner, text="Loomlet Launcher ещё не установлен на этом компьютере",
            font=ctk.CTkFont(size=14), text_color="gray"
        )
        self.subtitle.pack(pady=(0, 30))

        self.info = ctk.CTkLabel(
            self.inner,
            text="Нажмите «Установить», чтобы подготовить лаунчер к работе.\n"
                 "Будет создан файл-маркер, и при следующих запусках\n"
                 "это окно больше не появится.",
            font=ctk.CTkFont(size=13), justify="center"
        )
        self.info.pack(pady=(0, 30))

        self.install_btn = ctk.CTkButton(
            self.inner, text="УСТАНОВИТЬ", width=280, height=55,
            font=ctk.CTkFont(size=18, weight="bold"),
            fg_color="#1f6aa5", hover_color="#144870",
            command=self.do_install
        )
        self.install_btn.pack(pady=10)

        self.status = ctk.CTkLabel(
            self.inner, text="", font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.status.pack(pady=(20, 0))

    def do_install(self):
        self.install_btn.configure(state="disabled")
        self.status.configure(text="Установка...", text_color="gray")

        def task():
            try:
                with open(FIRST_RUN_MARKER, "w", encoding="utf-8") as f:
                    f.write("Loomlet Launcher installed.\n")
                self.after(0, lambda: self.status.configure(
                    text="Установлено! Переход к проверке компонентов...", text_color="#55ff55"
                ))
                self.after(800, self.on_installed)
            except Exception as e:
                self.after(0, lambda: self.status.configure(
                    text=f"Ошибка: {e}", text_color="#ff5555"
                ))
                self.after(0, lambda: self.install_btn.configure(state="normal"))

        threading.Thread(target=task, daemon=True).start()


# ================== ЭКРАН 2: ПРОВЕРКА КОМПОНЕНТОВ ==================

class CheckScreen(ctk.CTkFrame):
    def __init__(self, master, on_ready, on_cancel):
        super().__init__(master, fg_color="transparent")
        self.on_ready = on_ready
        self.on_cancel = on_cancel

        self.inner = ctk.CTkFrame(self, fg_color="transparent")
        self.inner.place(relx=0.5, rely=0.5, anchor="center")

        self.title = ctk.CTkLabel(
            self.inner, text="ПРОВЕРКА КОМПОНЕНТОВ",
            font=ctk.CTkFont(size=30, weight="bold")
        )
        self.title.pack(pady=(0, 10))

        self.subtitle = ctk.CTkLabel(
            self.inner, text="Проверяем наличие Java и файлов Gradle",
            font=ctk.CTkFont(size=14), text_color="gray"
        )
        self.subtitle.pack(pady=(0, 30))

        # --- Java ---
        self.java_frame = ctk.CTkFrame(self.inner, fg_color="#2a2a2a", corner_radius=10)
        self.java_frame.pack(fill="x", pady=5, padx=20)

        self.java_label = ctk.CTkLabel(
            self.java_frame, text="☕ Java (JDK 25)",
            font=ctk.CTkFont(size=16, weight="bold"), anchor="w"
        )
        self.java_label.pack(side="left", padx=15, pady=15)

        self.java_status = ctk.CTkLabel(
            self.java_frame, text="Проверка...",
            font=ctk.CTkFont(size=13), text_color="gray"
        )
        self.java_status.pack(side="left", padx=10)

        self.java_btn = ctk.CTkButton(
            self.java_frame, text="Установить", width=120, height=32,
            fg_color="#2a8ad4", hover_color="#1f6aa5",
            command=self.install_java
        )
        self.java_btn.pack(side="right", padx=15, pady=10)

        # --- Gradle ---
        self.gradle_frame = ctk.CTkFrame(self.inner, fg_color="#2a2a2a", corner_radius=10)
        self.gradle_frame.pack(fill="x", pady=5, padx=20)

        self.gradle_label = ctk.CTkLabel(
            self.gradle_frame, text="📦 Файлы Gradle",
            font=ctk.CTkFont(size=16, weight="bold"), anchor="w"
        )
        self.gradle_label.pack(side="left", padx=15, pady=15)

        self.gradle_status = ctk.CTkLabel(
            self.gradle_frame, text="Проверка...",
            font=ctk.CTkFont(size=13), text_color="gray"
        )
        self.gradle_status.pack(side="left", padx=10)

        self.gradle_btn = ctk.CTkButton(
            self.gradle_frame, text="Скачать", width=120, height=32,
            fg_color="#2a8ad4", hover_color="#1f6aa5",
            command=self.download_gradle
        )
        self.gradle_btn.pack(side="right", padx=15, pady=10)

        # --- Кнопки ---
        self.btn_frame = ctk.CTkFrame(self.inner, fg_color="transparent")
        self.btn_frame.pack(pady=(30, 0))

        self.cancel_btn = ctk.CTkButton(
            self.btn_frame, text="Отмена", width=140, height=45,
            fg_color="#555555", hover_color="#333333",
            command=self.on_cancel
        )
        self.cancel_btn.pack(side="left", padx=10)

        self.continue_btn = ctk.CTkButton(
            self.btn_frame, text="ПРОДОЛЖИТЬ", width=180, height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#1f6aa5", hover_color="#144870",
            command=self.on_ready,
            state="disabled"
        )
        self.continue_btn.pack(side="left", padx=10)

        # --- Прогресс ---
        self.progress = ctk.CTkProgressBar(self.inner, width=400, height=8)
        self.progress.set(0)
        self.progress.pack(pady=(20, 5))
        self.progress.pack_forget()

        self.status_label = ctk.CTkLabel(
            self.inner, text="", font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.status_label.pack(pady=(5, 0))

        # Запускаем проверку
        self.after(200, self.check_all)

    def check_all(self):
        java_ok = find_java_home() is not None
        gradle_ok = (os.path.exists(BUILD_GRADLE_PATH)
                     and os.path.getsize(BUILD_GRADLE_PATH) >= 100)

        # Java
        if java_ok:
            self.java_status.configure(text="✓ Установлена", text_color="#55ff55")
            self.java_btn.configure(state="disabled", text="Установлена")
        else:
            self.java_status.configure(text="✗ Не найдена", text_color="#ff5555")
            self.java_btn.configure(state="normal", text="Установить")

        # Gradle
        if gradle_ok:
            self.gradle_status.configure(text="✓ Найдены", text_color="#55ff55")
            self.gradle_btn.configure(state="disabled", text="Скачаны")
        else:
            self.gradle_status.configure(text="✗ Не найдены", text_color="#ff5555")
            self.gradle_btn.configure(state="normal", text="Скачать")

        # Кнопка «Продолжить»
        if java_ok and gradle_ok:
            self.continue_btn.configure(state="normal")

    def install_java(self):
        self.java_btn.configure(state="disabled", text="Установка...")
        self.java_status.configure(text="Установка JDK 25...", text_color="gray")
        self.status_label.configure(text="", text_color="gray")

        def task():
            ok = install_jdk25(status_callback=lambda t, error=False: self.after(
                0, lambda: self.status_label.configure(
                    text=t, text_color="#ff5555" if error else "gray"
                )
            ))
            self.after(0, self.check_all)
            if not ok:
                self.after(0, lambda: self.java_btn.configure(state="normal", text="Установить"))

        threading.Thread(target=task, daemon=True).start()

    def download_gradle(self):
        self.gradle_btn.configure(state="disabled", text="Скачивание...")
        self.gradle_status.configure(text="Скачивание...", text_color="gray")
        self.progress.pack(pady=(20, 5))
        self.progress.set(0)

        def task():
            ok = download_gradle_files(
                status_callback=lambda t, error=False: self.after(
                    0, lambda: self.status_label.configure(
                        text=t, text_color="#ff5555" if error else "gray"
                    )
                ),
                progress_callback=lambda p: self.after(0, lambda: self.progress.set(p / 100.0))
            )
            self.after(0, lambda: self.progress.pack_forget())
            self.after(0, self.check_all)
            if not ok:
                self.after(0, lambda: self.gradle_btn.configure(state="normal", text="Скачать"))

        threading.Thread(target=task, daemon=True).start()


# ================== ЭКРАН 3: ОСНОВНОЙ ЛАУНЧЕР ==================

class LauncherScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.game_process = None
        self.game_running = False

        # --- Левая панель ---
        self.left_frame = ctk.CTkFrame(self, width=340)
        self.left_frame.pack(side="left", fill="y", padx=10, pady=10)

        self.title_label = ctk.CTkLabel(
            self.left_frame, text="LOOMLET",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        self.title_label.pack(pady=(20, 0))

        self.subtitle = ctk.CTkLabel(
            self.left_frame, text="Minecraft Fabric Launcher",
            font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.subtitle.pack(pady=(0, 15))

        self.version_label = ctk.CTkLabel(self.left_frame, text="Версия Minecraft:")
        self.version_label.pack(pady=(5, 0))
        self.version_var = ctk.StringVar(value="26.3")
        self.version_menu = ctk.CTkOptionMenu(
            self.left_frame, values=["26.3"], variable=self.version_var, width=260
        )
        self.version_menu.pack(pady=5)

        self.nick_label = ctk.CTkLabel(self.left_frame, text="Ник игрока:")
        self.nick_label.pack(pady=(10, 0))
        self.nick_entry = ctk.CTkEntry(
            self.left_frame, width=260, height=38, placeholder_text="Введите ник"
        )
        self.nick_entry.pack(pady=5)

        self.play_button = ctk.CTkButton(
            self.left_frame, text="ИГРАТЬ", width=260, height=50,
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self.on_play_clicked,
            fg_color="#1f6aa5", hover_color="#144870"
        )
        self.play_button.pack(pady=(15, 5))

        self.stop_button = ctk.CTkButton(
            self.left_frame, text="ВЫКЛЮЧИТЬ ИГРУ", width=260, height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.on_stop_clicked,
            fg_color="#a83232", hover_color="#7a2020",
            state="disabled"
        )
        self.stop_button.pack(pady=5)

        self.open_mods_btn = ctk.CTkButton(
            self.left_frame, text="📁 Открыть папку с модами",
            width=260, height=32, command=self.open_mods_folder,
            fg_color="#333333", hover_color="#444444"
        )
        self.open_mods_btn.pack(pady=(15, 3))

        self.open_game_btn = ctk.CTkButton(
            self.left_frame, text="📂 Открыть папку игры",
            width=260, height=32, command=self.open_game_folder,
            fg_color="#333333", hover_color="#444444"
        )
        self.open_game_btn.pack(pady=3)

        self.open_log_btn = ctk.CTkButton(
            self.left_frame, text="📜 Открыть лог игры",
            width=260, height=32, command=self.open_log_file,
            fg_color="#333333", hover_color="#444444"
        )
        self.open_log_btn.pack(pady=3)

        self.reload_btn = ctk.CTkButton(
            self.left_frame, text="🔄 Перезагрузить файлы Gradle",
            width=260, height=32, command=self.reload_gradle,
            fg_color="#333333", hover_color="#444444"
        )
        self.reload_btn.pack(pady=3)

        self.progress = ctk.CTkProgressBar(self.left_frame, width=260, height=8)
        self.progress.set(0)
        self.progress.pack(pady=(10, 0))
        self.progress.pack_forget()

        self.status_label = ctk.CTkLabel(
            self.left_frame, text="Готов к запуску",
            font=ctk.CTkFont(size=11), text_color="gray"
        )
        self.status_label.pack(side="bottom", pady=10)

        # --- Правая панель (лог) ---
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)

        self.log_title = ctk.CTkLabel(
            self.right_frame, text="Консоль Gradle / Minecraft",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.log_title.pack(pady=(10, 5))

        self.log_box = ctk.CTkTextbox(
            self.right_frame, width=380, height=560,
            font=ctk.CTkFont(size=11, family="Consolas"),
            wrap="word"
        )
        self.log_box.pack(padx=10, pady=(0, 10), fill="both", expand=True)
        self.log_box.configure(state="disabled")

        # Горячие клавиши — привязываем к главному окну
        top = self.winfo_toplevel()
        top.bind("<Return>", lambda e: self.on_play_clicked())
        top.bind("<Escape>", lambda e: self.on_stop_clicked())

    # ---------- Логика ----------
    def on_play_clicked(self):
        if self.game_running:
            self.set_status("Игра уже запущена", error=True)
            return

        nick = self.nick_entry.get().strip()
        if not nick:
            self.set_status("Введите ник!", error=True)
            return
        if not re.match(r"^[A-Za-z0-9_]{3,16}$", nick):
            self.set_status("Ник: 3–16 символов, буквы/цифры/_", error=True)
            return

        if not find_java_home():
            self.set_status("Java не найдена! Перезапустите лаунчер.", error=True)
            return

        if (not os.path.exists(BUILD_GRADLE_PATH)
                or os.path.getsize(BUILD_GRADLE_PATH) < 100):
            self.set_status("Файлы Gradle не найдены! Перезапустите лаунчер.", error=True)
            return

        self._start_launch(nick)

    def on_stop_clicked(self):
        if not self.game_running or self.game_process is None:
            self.set_status("Игра не запущена", error=True)
            return

        self.set_status("Остановка игры...")
        self.stop_button.configure(state="disabled")

        def killer():
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.game_process.pid)],
                    capture_output=True, shell=True
                )
            except Exception as e:
                self.append_log(f"Ошибка остановки: {e}\n")
            finally:
                self.game_running = False
                self.game_process = None
                self.after(0, lambda: self.play_button.configure(state="normal"))
                self.after(0, lambda: self.stop_button.configure(state="disabled"))
                self.set_status("Игра остановлена")

        threading.Thread(target=killer, daemon=True).start()

    def _start_launch(self, nick: str):
        self.play_button.configure(state="disabled")
        self.set_status("Подготовка...")
        thread = threading.Thread(target=self.launch_game, args=(nick,), daemon=True)
        thread.start()

    def launch_game(self, nick: str):
        try:
            self.set_status("Запись ника в build.gradle...")
            set_username_in_build_gradle(nick)

            self.set_status(f"Запуск Minecraft как {nick}...")
            gradlew_path = os.path.join(GRADLE_DIR, "gradlew.bat")

            if not os.path.exists(gradlew_path):
                self.set_status("gradlew.bat не найден!", error=True)
                return

            self.game_running = True
            self.stop_button.configure(state="normal")

            self.game_process = subprocess.Popen(
                [gradlew_path, "runClient", "--no-configuration-cache", "--info"],
                cwd=GRADLE_DIR,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            for line in self.game_process.stdout:
                self.append_log(line)

            self.game_process.wait()

            if self.game_process.returncode == 0:
                self.set_status("Игра закрыта")
            else:
                self.set_status(f"Gradle завершился с кодом {self.game_process.returncode}", error=True)
                self.append_log(
                    f"\n[ОШИБКА] Gradle вернул код {self.game_process.returncode}.\n"
                    f"Смотрите лог выше или откройте {LOG_FILE}\n"
                )

        except Exception as e:
            self.set_status(f"Ошибка: {e}", error=True)
            self.append_log(f"\n[ИСКЛЮЧЕНИЕ] {e}\n")
        finally:
            self.game_running = False
            self.game_process = None
            self.after(0, lambda: self.play_button.configure(state="normal"))
            self.after(0, lambda: self.stop_button.configure(state="disabled"))

    # ---------- Утилиты ----------
    def set_progress(self, percent: int):
        self.after(0, lambda: self.progress.set(percent / 100.0))

    def set_status(self, text: str, error: bool = False):
        color = "#ff5555" if error else "gray"
        self.after(0, lambda: self.status_label.configure(text=text, text_color=color))

    def append_log(self, text: str):
        def _update():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", text)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _update)

    def open_mods_folder(self):
        os.makedirs(MODS_DIR, exist_ok=True)
        os.startfile(MODS_DIR)

    def open_game_folder(self):
        os.makedirs(GRADLE_DIR, exist_ok=True)
        os.startfile(GRADLE_DIR)

    def open_log_file(self):
        if os.path.exists(LOG_FILE):
            os.startfile(LOG_FILE)
        else:
            self.set_status("Лог игры ещё не создан", error=True)

    def reload_gradle(self):
        def task():
            self.set_status("Перезагрузка файлов Gradle...")
            if download_gradle_files(
                status_callback=lambda t, error=False: self.set_status(t, error),
                progress_callback=self.set_progress
            ):
                clean_gradle_cache(status_callback=lambda t, error=False: self.set_status(t, error))
                self.set_status("Файлы Gradle перезагружены")
            else:
                self.set_status("Ошибка перезагрузки", error=True)
        threading.Thread(target=task, daemon=True).start()


# ================== ГЛАВНОЕ ОКНО ==================

class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Loomlet Launcher")
        self.geometry("780x680")
        self.resizable(False, False)

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        if not os.path.exists(FIRST_RUN_MARKER):
            self.show_first_run()
        else:
            self.show_check()

    def _clear(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def show_first_run(self):
        self._clear()
        screen = FirstRunScreen(self.container, on_installed=self.show_check)
        screen.pack(fill="both", expand=True)

    def show_check(self):
        self._clear()
        screen = CheckScreen(
            self.container,
            on_ready=self.show_launcher,
            on_cancel=self.show_first_run
        )
        screen.pack(fill="both", expand=True)

    def show_launcher(self):
        self._clear()
        screen = LauncherScreen(self.container)
        screen.pack(fill="both", expand=True)


if __name__ == "__main__":
    app = LauncherApp()
    app.mainloop()
