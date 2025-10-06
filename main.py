import tkinter as tk
from gui import EditorGUI  # <-- MUDANÇA IMPORTANTE AQUI

def main():
    """Cria a janela principal e inicia a aplicação."""
    root = tk.Tk()
    root.geometry("1200x800") # Define um tamanho inicial bom para a janela
    app = EditorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
