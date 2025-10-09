import tkinter as tk
from tkinter import font

# Importa as classes das interfaces gráficas
from gui import EditorGUI
from gui_mealy import MealyGUI

class MainMenu:
    def __init__(self, root):
        self.root = root
        self.root.title("Seleção de Ferramenta")
        self.root.geometry("400x300")
        
        # Centraliza a janela
        self.root.eval('tk::PlaceWindow . center')

        # Frame principal para conter os widgets
        main_frame = tk.Frame(root, padx=20, pady=20)
        main_frame.pack(expand=True)

        # Título
        title_font = font.Font(family="Helvetica", size=16, weight="bold")
        label = tk.Label(main_frame, text="Selecione o Editor", font=title_font)
        label.pack(pady=(0, 20))

        # Botões
        button_font = font.Font(family="Helvetica", size=12)
        
        btn_automaton = tk.Button(main_frame,
                                  text="Editor de Autômatos Finitos",
                                  font=button_font,
                                  command=self.launch_automaton_editor,
                                  width=30, height=2)
        btn_automaton.pack(pady=10)

        btn_mealy = tk.Button(main_frame,
                              text="Editor de Máquinas de Mealy",
                              font=button_font,
                              command=self.launch_mealy_editor,
                              width=30, height=2)
        btn_mealy.pack(pady=10)

    def launch_automaton_editor(self):
        """Cria uma nova janela (Toplevel) para o editor de autômatos."""
        automaton_window = tk.Toplevel(self.root)
        app = EditorGUI(automaton_window)

    def launch_mealy_editor(self):
        """Cria uma nova janela (Toplevel) para o editor de Mealy."""
        mealy_window = tk.Toplevel(self.root)
        app = MealyGUI(mealy_window)

def main():
    root = tk.Tk()
    app = MainMenu(root)
    root.mainloop()

if __name__ == "__main__":
    main()
