import tkinter as tk
from tkinter import font
from tkinter import ttk
import io
import os
import ctypes
import urllib.request
from PIL import Image, ImageTk

from gui.gui_automato import EditorGUI
from gui.gui_mealy import MealyGUI
from gui.gui_moore import MooreGUI
from gui.gui_pilha import PilhaGUI
from gui.gui_turing import TuringGUI # <-- ADICIONADO
import sv_ttk

class MainMenu:
    def __init__(self, root):
        self.root = root
        self.root.title("IC-Tômato++")
        self.root.geometry("500x750") # <-- Aumentei um pouco a altura para o novo botão
        
        # Centraliza a janela
        self.root.eval('tk::PlaceWindow . center')

        # Frame principal para conter os widgets
        main_frame = tk.Frame(root, padx=20, pady=20)
        main_frame.pack(expand=True)

        self.load_logo()

        # Título
        title_font = font.Font(family="Helvetica", size=28, weight="bold")
        subtitle_font = font.Font(family="Helvetica", size=16, weight="bold")

        # Canvas para o título com efeito de brilho
        title_canvas = tk.Canvas(main_frame, height=60, bg=main_frame.cget('bg'), highlightthickness=0)
        title_canvas.pack(pady=(0, 5))

        # Efeito de brilho (desenhando o texto com deslocamento)
        glow_color = "#ffc107" # Amarelo do brilho
        for i in range(1, 3):
            title_canvas.create_text(200 - i, 30 - i, text="IC-Tômato++", font=title_font, fill=glow_color, anchor='center')
            title_canvas.create_text(200 + i, 30 + i, text="IC-Tômato++", font=title_font, fill=glow_color, anchor='center')

        # Texto principal do título
        title_canvas.create_text(200, 30, text="IC-Tômato++", font=title_font, fill="white", anchor='center')

        label = ttk.Label(main_frame, text="Selecione o Editor", font=subtitle_font)
        label.pack(pady=(0, 25))

        # --- Botões customizados ---
        self.create_menu_option(
            main_frame,
            text="Editor de Autômatos Finitos",
            command=self.launch_automaton_editor
        )

        self.create_menu_option(
            main_frame,
            text="Editor de Máquinas de Mealy",
            command=self.launch_mealy_editor
        )

        self.create_menu_option(
            main_frame,
            text="Editor de Máquinas de Moore",
            command=self.launch_moore_editor
        )

        self.create_menu_option(
            main_frame,
            text="Editor de Autômatos de Pilha",
            command=self.launch_pda_editor
        )
        
        # --- BOTÃO ADICIONADO ---
        self.create_menu_option(
            main_frame,
            text="Editor de Máquinas de Turing",
            command=self.launch_turing_editor
        )
        # ------------------------

    def create_menu_option(self, parent, text, command):
        """Cria um botão customizado com efeito de hover."""
        # Cores
        NORMAL_BG = "#ffc107"  # Amarelo
        HOVER_BG = "#007bff"   # Azul
        NORMAL_FG = "#212529"  # Preto suave
        HOVER_FG = "white"     # Branco

        # Frame que serve como o "quadrado"
        frame = tk.Frame(parent, bg=NORMAL_BG)
        frame.pack(pady=10, fill='x')

        label = tk.Label(frame, text=text, bg=NORMAL_BG, fg=NORMAL_FG,
                         font=("Helvetica", 12, "bold"), pady=25, cursor="hand2")
        label.pack(fill='x')

        # Efeitos de Hover (passar o mouse)
        frame.bind("<Enter>", lambda e: (frame.config(bg=HOVER_BG), label.config(bg=HOVER_BG, fg=HOVER_FG)))
        frame.bind("<Leave>", lambda e: (frame.config(bg=NORMAL_BG), label.config(bg=NORMAL_BG, fg=NORMAL_FG)))
        
        # Ação de clique
        frame.bind("<Button-1>", lambda e: command())
        label.bind("<Button-1>", lambda e: command())

    def launch_automaton_editor(self):
        """Cria uma nova janela (Toplevel) para o editor de autômatos."""
        self.open_editor_window(EditorGUI)

    def launch_mealy_editor(self):
        """Cria uma nova janela (Toplevel) para o editor de Mealy."""
        self.open_editor_window(MealyGUI)

    def launch_moore_editor(self):
        """Cria uma nova janela para o editor de Moore."""
        self.open_editor_window(MooreGUI)

    def launch_pda_editor(self):
        """Cria uma nova janela para o editor de Autômatos de Pilha."""
        self.open_editor_window(PilhaGUI)

    # --- FUNÇÃO ADICIONADA ---
    def launch_turing_editor(self):
        """Cria uma nova janela para o editor de Máquinas de Turing."""
        self.open_editor_window(TuringGUI)
    # -------------------------

    def load_logo(self):
        """Carrega e exibe o logo no canto superior direito."""
        # Tenta usar o ícone local primeiro (mais rápido e sem depender de rede)
        icon_path = os.path.join(os.path.dirname(__file__), "icons", "icon.ico")
        try:
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
                display_img = image.resize((80, 80), Image.Resampling.LANCZOS)
                icon_img = image.resize((32, 32), Image.Resampling.LANCZOS)

                self.logo_image = ImageTk.PhotoImage(display_img)
                self.icon_image = ImageTk.PhotoImage(icon_img)

                # Aplica o .ico como ícone do aplicativo no Windows (e em outras plataformas quando suportado)
                try:
                    self.root.iconbitmap(icon_path)
                except Exception:
                    # fallback para iconphoto
                    try:
                        self.root.iconphoto(False, self.icon_image)
                    except Exception:
                        pass

                logo_label = tk.Label(self.root, image=self.logo_image, bg=self.root.cget('bg'))
                logo_label.place(relx=1.0, y=10, x=-10, anchor='ne')
                # armazena o caminho para uso em outras janelas
                self.icon_path = icon_path
                return

            # Se o ícone local não existir, tenta baixar a imagem remota como antes
            url = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT_Iz4iLTCkvEbHl93acer5aym3CcSl5CHMBg&s"
            with urllib.request.urlopen(url) as response:
                image_data = response.read()
            image = Image.open(io.BytesIO(image_data))
            display_img = image.resize((80, 80), Image.Resampling.LANCZOS)
            icon_img = image.resize((32, 32), Image.Resampling.LANCZOS)

            self.logo_image = ImageTk.PhotoImage(display_img)
            self.icon_image = ImageTk.PhotoImage(icon_img)
            try:
                self.root.iconphoto(False, self.icon_image)
            except Exception:
                pass
            logo_label = tk.Label(self.root, image=self.logo_image, bg=self.root.cget('bg'))
            logo_label.place(relx=1.0, y=10, x=-10, anchor='ne')
            self.icon_path = None

        except Exception as e:
            print(f"Não foi possível carregar o logo: {e}")

    def open_editor_window(self, EditorClass):
        """Oculta o menu principal e abre o editor passado como classe.

        Ao fechar a janela do editor, o menu principal é restaurado.
        """
        # Oculta a janela principal
        try:
            self.root.withdraw()
        except Exception:
            pass

        editor_window = tk.Toplevel(self.root)
        # Aplica o mesmo ícone ao editor (se disponível)
        try:
            # Prioriza .ico local via iconbitmap (bom no Windows)
            if hasattr(self, 'icon_path') and self.icon_path:
                try:
                    editor_window.iconbitmap(self.icon_path)
                except Exception:
                    # fallback para PhotoImage
                    if hasattr(self, 'icon_image'):
                        editor_window.iconphoto(False, self.icon_image)
            else:
                if hasattr(self, 'icon_image'):
                    editor_window.iconphoto(False, self.icon_image)
        except Exception:
            pass
        editor_app = EditorClass(editor_window)

        # Quando o editor for fechado, reexibe a janela principal
        def on_close():
            try:
                editor_window.destroy()
            except Exception:
                pass
            try:
                self.root.deiconify()
            except Exception:
                pass

        editor_window.protocol("WM_DELETE_WINDOW", on_close)

def main():
    root = tk.Tk()

    try:
        # Melhora a resolução em telas com alta densidade de pixels (HiDPI) no Windows
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass # Ignora o erro se não estiver no Windows ou a função não estiver disponível

    # Aplica um tema moderno (light ou dark)
    sv_ttk.set_theme("light")
    
    app = MainMenu(root)
    root.mainloop()

if __name__ == "__main__":
    main()