import tkinter as tk
from tkinter import font
from tkinter import ttk
import io
import ctypes
import urllib.request
from PIL import Image, ImageTk

from gui import EditorGUI
from gui_mealy import MealyGUI
from gui_moore import MooreGUI
from gui_pilha import PilhaGUI
import sv_ttk

class MainMenu:
    def __init__(self, root):
        self.root = root
        self.root.title("IC-Tômato++")
        self.root.geometry("500x650")
        
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
        automaton_window = tk.Toplevel(self.root)
        app = EditorGUI(automaton_window)

    def launch_mealy_editor(self):
        """Cria uma nova janela (Toplevel) para o editor de Mealy."""
        mealy_window = tk.Toplevel(self.root)
        app = MealyGUI(mealy_window)

    def launch_moore_editor(self):
        """Cria uma nova janela para o editor de Moore."""
        moore_window = tk.Toplevel(self.root)
        app = MooreGUI(moore_window)

    def launch_pda_editor(self):
        """Cria uma nova janela para o editor de Autômatos de Pilha."""
        pda_window = tk.Toplevel(self.root)
        app = PilhaGUI(pda_window)

    def load_logo(self):
        """Carrega e exibe o logo no canto superior direito."""
        try:
            url = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT_Iz4iLTCkvEbHl93acer5aym3CcSl5CHMBg&s"
            with urllib.request.urlopen(url) as response:
                image_data = response.read()
            
            image = Image.open(io.BytesIO(image_data))
            image = image.resize((80, 80), Image.Resampling.LANCZOS)
            
            # Mantém uma referência para a imagem para evitar que seja coletada pelo garbage collector
            self.logo_image = ImageTk.PhotoImage(image)
            
            logo_label = tk.Label(self.root, image=self.logo_image, bg=self.root.cget('bg'))
            # Usa place() para posicionamento absoluto no canto superior direito
            logo_label.place(relx=1.0, y=10, x=-10, anchor='ne')

        except Exception as e:
            print(f"Não foi possível carregar o logo: {e}")

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
