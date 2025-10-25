#!/usr/bin/env python3
"""
gui_pilha.py - Interface para Autômatos de Pilha (PDA).
"""
import os
import math
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox, ttk
from collections import defaultdict
from typing import Dict, Tuple, List, Set # Import Set

# Importações de PIL
from PIL import Image, ImageTk, ImageEnhance

# Importações do módulo do autômato de pilha
from core.pilha import AutomatoPilha, EPSILON, snapshot_of_pda, restore_from_pda_snapshot

# --- CONSTANTES ---
STATE_RADIUS = 24 # Raio visual dos estados
FONT = ("Helvetica", 13) # <-- FONTE AUMENTADA
ANIM_MS = 500 # Milissegundos para animação da simulação

# -------------------------
# Classe Tooltip (Dica de Ferramenta)
# -------------------------
class Tooltip:
    """ Cria um tooltip (dica de ferramenta) para um widget. """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        """ Mostra a janela do tooltip perto do cursor. """
        if not self.widget.winfo_exists(): return
        x = self.widget.winfo_pointerx() + 15
        y = self.widget.winfo_pointery() + 10

        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(tw, text=self.text, justify='left',
                       background="#ffffe0", relief='solid', borderwidth=1,
                       font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tooltip(self, event=None):
        """ Esconde a janela do tooltip. """
        tw = self.tooltip_window
        self.tooltip_window = None
        if tw:
            try: tw.destroy()
            except tk.TclError: pass

# -------------------------
# Classe Principal da GUI para PDA
# -------------------------
class PilhaGUI:
    """ Classe principal da interface gráfica para Autômatos de Pilha. """
    def __init__(self, root: tk.Toplevel):
        self.root = root
        root.title("Editor de Autômatos de Pilha")
        try:
            root.state('zoomed')
        except tk.TclError:
            root.geometry("1100x750")

        # Estilo ttk
        style = ttk.Style()
        style.configure("TButton", padding=(15, 12))
        style.configure("Accent.TButton", padding=(15, 12))
        style.configure("TMenubutton", padding=(15, 12))
        style.configure("Toolbutton", padding=(10, 8), relief="flat")
        style.map("Toolbutton", background=[('active', '#e0e0e0')])

        # Dados
        self.automato = AutomatoPilha()
        self.positions: Dict[str, Tuple[int, int]] = {}
        self.mode = "select"
        self.dragging = None
        self.mode_buttons: Dict[str, tk.Widget] = {}
        self.transition_src = None
        self.pinned_mode = "select"
        self.icons: Dict[str, ImageTk.PhotoImage] = {}
        self.edge_widgets: Dict[Tuple[str, str], Dict] = {}

        # Undo/Redo
        self.undo_stack: List[str] = []
        self.redo_stack: List[str] = []

        # Simulação
        # ***** MODIFICADO *****
        # Histórico: Lista de (estado, input_idx_consumido, pilha_tupla)
        self.history: List[Tuple[str, int, Tuple]] = []
        # **********************
        self.sim_step = 0
        self.sim_playing = False
        self.result_indicator = None # Aceito/Rejeitado
        self.current_input_string = "" # Guarda a string de entrada da simulação

        # Transformação (zoom/pan)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_last = None
        self.current_filepath = None

        # Construção UI
        self._build_toolbar()
        self._build_canvas()
        self._build_bottom_bar()
        self._build_statusbar()
        self._bind_events()

        self.root.after(100, self.center_view)
        self._push_undo_snapshot()
        self.draw_all()

    def center_view(self):
         """ Centraliza a visualização no canvas. """
         if not self.positions:
             try:
                 canvas_width = self.canvas.winfo_width(); canvas_height = self.canvas.winfo_height()
                 self.offset_x = canvas_width / 2 - (100 * self.scale)
                 self.offset_y = canvas_height / 2 - (100 * self.scale)
             except tk.TclError: self.offset_x, self.offset_y = 100, 100
         elif self.positions:
             avg_x = sum(p[0] for p in self.positions.values()) / len(self.positions)
             avg_y = sum(p[1] for p in self.positions.values()) / len(self.positions)
             try:
                 canvas_width = self.canvas.winfo_width(); canvas_height = self.canvas.winfo_height()
                 self.offset_x = canvas_width / 2 - (avg_x * self.scale)
                 self.offset_y = canvas_height / 2 - (avg_y * self.scale)
             except tk.TclError:
                 self.offset_x = 100 - avg_x * self.scale; self.offset_y = 100 - avg_y * self.scale
         self.draw_all()

    def _build_toolbar(self):
        """ Constrói a barra de ferramentas superior. """
        toolbar = tk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5, 10))

        file_menu = tk.Menu(toolbar, tearoff=0)
        file_menu.add_command(label="Abrir...", command=self.cmd_open)
        file_menu.add_command(label="Salvar", command=self.cmd_save)
        file_menu.add_command(label="Salvar Como...", command=self.cmd_save_as)
        self._create_toolbar_menubutton(toolbar, "arquivo", "Arquivo", file_menu)
        ttk.Separator(toolbar, orient='vertical').pack(side=tk.LEFT, padx=8, fill='y')

        self._create_toolbar_button(toolbar, "novo_estado", "Novo Estado", self.cmd_add_state)
        self._create_toolbar_button(toolbar, "nova_transicao", "Nova Transição", self.cmd_add_transition)
        self._create_toolbar_button(toolbar, "definir_inicio", "Definir Início", self.cmd_set_start)
        self._create_toolbar_button(toolbar, "alternar_final", "Alternar Final", self.cmd_toggle_final)
        self._create_toolbar_button(toolbar, "excluir_estado", "Excluir Estado", self.cmd_delete_state_mode)
        # --- NOVO BOTÃO ---
        self._create_toolbar_button(toolbar, "excluir_transicao", "Excluir Transição", self.cmd_delete_transition_mode)
        # ------------------
        ttk.Separator(toolbar, orient='vertical').pack(side=tk.LEFT, padx=8, fill='y')

        export_menu = tk.Menu(toolbar, tearoff=0)
        export_menu.add_command(label="Exportar para TikZ (.tex)", command=self.cmd_export_tikz)
        export_menu.add_command(label="Exportar para SVG (.svg)", command=self.cmd_export_svg)
        export_menu.add_command(label="Exportar para PNG (.png)", command=self.cmd_export_png)
        self._create_toolbar_menubutton(toolbar, "exportar", "Exportar", export_menu)

        self.mode_label = ttk.Label(toolbar, text="Modo: Selecionar", font=("Helvetica", 11, "bold"))
        self.mode_label.pack(side=tk.RIGHT, padx=10)

    def _create_toolbar_menubutton(self, parent, icon_name, tooltip_text, menu):
        """ Cria um botão de menu na toolbar. """
        icon_path = os.path.join("icons", f"{icon_name}.png")
        try:
            img = Image.open(icon_path).convert("RGBA")
            img = img.resize((40, 40), Image.Resampling.LANCZOS)
            self.icons[icon_name] = ImageTk.PhotoImage(img)
            button = ttk.Menubutton(parent, image=self.icons[icon_name], style="Toolbutton")
        except Exception as e:
            print(f"Erro ao carregar ícone '{icon_path}': {e}. Usando texto.")
            button = ttk.Menubutton(parent, text=tooltip_text)
        button["menu"] = menu
        button.pack(side=tk.LEFT, padx=2)
        Tooltip(button, tooltip_text)
        self.mode_buttons[icon_name] = button

    def _create_toolbar_button(self, parent, icon_name, tooltip_text, command):
        """ Cria um botão normal na toolbar. """
        icon_path = os.path.join("icons", f"{icon_name}.png")
        try:
            img = Image.open(icon_path).convert("RGBA")
            img = img.resize((40, 40), Image.Resampling.LANCZOS)
            self.icons[icon_name] = ImageTk.PhotoImage(img)
            button = ttk.Button(parent, image=self.icons[icon_name], command=command, style="Toolbutton")
        except Exception as e:
            print(f"Erro ao carregar ícone '{icon_path}': {e}. Usando texto.")
            button = ttk.Button(parent, text=tooltip_text, command=command)
        button.pack(side=tk.LEFT, padx=2)
        self.mode_buttons[icon_name] = button
        Tooltip(button, tooltip_text)

        # ***** INÍCIO DA CORREÇÃO *****
        button.bind("<Enter>", lambda e, m=icon_name: self._set_mode(m, pinned=False), add='+')
        button.bind("<Leave>", lambda e: self._set_mode(self.pinned_mode, pinned=False), add='+')
        # ***** FIM DA CORREÇÃO *****

    def _build_canvas(self):
        """ Constrói o canvas principal. """
        self.canvas = tk.Canvas(self.root, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=0)

    def _build_bottom_bar(self):
        """ Constrói a barra inferior com entrada e controles de simulação. """
        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        ttk.Label(bottom, text="Entrada:", font=("Helvetica", 10)).pack(side=tk.LEFT)
        self.input_entry = ttk.Entry(bottom, width=40, font=("Helvetica", 11))
        self.input_entry.pack(side=tk.LEFT, padx=5, ipady=5)

        ttk.Button(bottom, text="Simular", command=self.cmd_start_simulation, style="Accent.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Passo", command=self.cmd_step).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Play/Pausar", command=self.cmd_play_pause).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Reiniciar", command=self.cmd_reset_sim).pack(side=tk.LEFT, padx=2)

        self.sim_display_canvas = tk.Canvas(bottom, height=60, bg="#f0f0f0", highlightthickness=1, highlightbackground="#cccccc")
        self.sim_display_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

    def _build_statusbar(self):
        """ Constrói a barra de status. """
        self.status = tk.Label(self.root, text="Pronto", anchor="w", relief=tk.SUNKEN, padx=5)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def _bind_events(self):
        """ Associa eventos a handlers. """
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel)
        self.canvas.bind("<Button-5>", self.on_mousewheel)
        self.canvas.bind("<Button-2>", self.on_middle_press)
        self.canvas.bind("<B2-Motion>", self.on_middle_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_middle_release)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())


    def _update_mode_button_styles(self):
        """ Atualiza estilo dos botões da toolbar baseado no modo pinado. """
        for name, btn in self.mode_buttons.items():
            base_name = name.replace("_src", "").replace("_dst", "")
            is_pinned = (base_name == self.pinned_mode.replace("_src", "").replace("_dst", ""))
            if isinstance(btn, (ttk.Button, ttk.Menubutton)):
                 btn.config(style="Accent.TButton" if is_pinned else "TButton")


    def _set_mode(self, new_mode, pinned=False):
        """ Define o modo de operação e atualiza UI. """
        if pinned:
            # Se clicar no botão já ativo, desativa (volta para 'select')
            if self.pinned_mode == new_mode:
                self.pinned_mode = "select"
                new_mode = "select" # Atualiza o modo corrente também
            else: # Senão, ativa o novo modo
                self.pinned_mode = new_mode
        self.mode = new_mode # Atualiza sempre o modo corrente (para hover)


        cursor_map = { # Cursor do mouse
            "add_state": "crosshair", "add_transition_src": "hand2",
            "add_transition_dst": "hand2", "set_start": "hand2",
            "toggle_final": "hand2", "delete_state": "X_cursor",
            "delete_transition": "X_cursor" # Novo
        }
        mode_text_map = { # Texto do rótulo
            "select": "Modo: Selecionar", "add_state": "Modo: Adicionar Estado",
            "add_transition_src": "Modo: Adicionar Transição (Origem)",
            "add_transition_dst": "Modo: Adicionar Transição (Destino)",
            "set_start": "Modo: Definir Início", "toggle_final": "Modo: Alternar Final",
            "delete_state": "Modo: Excluir Estado",
            "delete_transition": "Modo: Excluir Transição" # Novo
        }
        # Usa self.pinned_mode para o cursor e texto, pois self.mode pode ser temporário (hover)
        self.canvas.config(cursor=cursor_map.get(self.pinned_mode, "arrow"))
        self.mode_label.config(text=mode_text_map.get(self.pinned_mode, "Modo: Selecionar"))
        self._update_mode_button_styles()

    # --- DIÁLOGO CUSTOMIZADO (HELPER) ---
    def _ask_custom_string(self, title, prompt, initial_value=""):
        """
        Cria um diálogo Toplevel customizado para substituir simpledialog.askstring.
        Retorna a string inserida ou None se cancelado.
        """
        result_val = [None] # Usa lista para ser mutável

        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("400x200") # Tamanho maior
        dialog.transient(self.root)
        dialog.grab_set()

        # Adiciona fonte maior ao Label
        tk.Label(dialog, text=prompt, justify="left", font=("Helvetica", 12)).pack(pady=10, padx=10)
        
        # Adiciona fonte maior ao Entry
        entry = ttk.Entry(dialog, width=50, font=("Helvetica", 12))
        entry.pack(pady=5, padx=10, fill="x", expand=True)
        entry.insert(0, initial_value)
        entry.focus_set()

        def on_ok():
            result_val[0] = entry.get()
            dialog.destroy()

        def on_cancel():
            dialog.destroy() # result_val[0] permanece None
            
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="OK", command=on_ok, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        dialog.bind("<Return>", lambda e: on_ok())
        dialog.bind("<Escape>", lambda e: on_cancel())

        dialog.wait_window()
        return result_val[0]
    # --- FIM DO DIÁLOGO CUSTOMIZADO ---

    # --- Comandos Botões ---
    def cmd_add_state(self): self._set_mode("add_state", pinned=True); self.status.config(text="Clique no canvas para adicionar estado.")
    def cmd_add_transition(self): self._set_mode("add_transition_src", pinned=True); self.transition_src=None; self.status.config(text="Clique no estado de origem.")
    def cmd_set_start(self): self._set_mode("set_start", pinned=True); self.status.config(text="Clique no estado inicial.")
    def cmd_toggle_final(self): self._set_mode("toggle_final", pinned=True); self.status.config(text="Clique no estado para alternar final/não final.")
    def cmd_delete_state_mode(self): self._set_mode("delete_state", pinned=True); self.status.config(text="Clique em um estado para excluí-lo.")
    # --- NOVO COMANDO ---
    def cmd_delete_transition_mode(self): self._set_mode("delete_transition", pinned=True); self.status.config(text="Clique no rótulo de uma transição para excluí-la.")
    # ------------------

    # --- Comandos Arquivo/Exportar ---
    def cmd_open(self):
        path = filedialog.askopenfilename(defaultextension=".json", filetypes=[("PDA Files", "*.json"), ("All", "*.*")])
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f: snapshot = f.read()
            self.automato, self.positions = restore_from_pda_snapshot(snapshot)
            self.current_filepath = path; self.root.title(f"Editor PDA - {os.path.basename(path)}")
            self.undo_stack = [snapshot]; self.redo_stack.clear()
            self.draw_all(); self.center_view()
            self.status.config(text=f"Arquivo '{os.path.basename(path)}' carregado.")
        except Exception as e: messagebox.showerror("Erro Abrir", f"Falha:\n{e}", parent=self.root)

    def cmd_save(self):
        if not self.current_filepath: self.cmd_save_as()
        else:
            try:
                # Usa o snapshot mais recente da pilha de undo para salvar
                snap = snapshot_of_pda(self.automato, self.positions)
                with open(self.current_filepath, "w", encoding="utf-8") as f:
                    f.write(snap)
                # Garante que o estado salvo esteja no topo do undo
                if not self.undo_stack or self.undo_stack[-1] != snap:
                    self.undo_stack.append(snap)
                    if len(self.undo_stack) > 50: self.undo_stack.pop(0)
                    self.redo_stack.clear() # Limpa redo ao salvar
                self.status.config(text=f"Salvo em '{os.path.basename(self.current_filepath)}'.")
            except Exception as e: messagebox.showerror("Erro Salvar", f"Falha:\n{e}", parent=self.root)

    def cmd_save_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("PDA Files", "*.json"), ("All", "*.*")])
        if not path: return
        self.current_filepath = path; self.root.title(f"Editor PDA - {os.path.basename(path)}")
        self.cmd_save()

    def cmd_export_tikz(self): messagebox.showinfo("Exportar", "Exportação TikZ não implementada para PDA.", parent=self.root)
    def cmd_export_svg(self):
        path = filedialog.asksaveasfilename(defaultextension=".svg", filetypes=[("SVG", "*.svg")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f: f.write(self._generate_svg_text())
                messagebox.showinfo("Exportar", f"SVG exportado para {path}", parent=self.root)
            except Exception as e: messagebox.showerror("Erro SVG", f"Falha:\n{e}", parent=self.root)

    def cmd_export_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not path: return
        svg = self._generate_svg_text()
        try:
            import cairosvg
            cairosvg.svg2png(bytestring=svg.encode('utf-8'), write_to=path)
            messagebox.showinfo("Exportar PNG", f"PNG salvo em {path}", parent=self.root)
        except ImportError: messagebox.showwarning("Exportar PNG", "'cairosvg' não instalado.\nUse: pip install cairosvg", parent=self.root)
        except Exception as e: messagebox.showerror("Erro PNG", f"Falha:\n{e}", parent=self.root)

    def _generate_svg_text(self): return '<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg"></svg>' # Placeholder

    # --- Comandos Simulação ---
    # ***** INÍCIO DA MODIFICAÇÃO *****
    def cmd_start_simulation(self):
        self.current_input_string = self.input_entry.get() # Guarda a string
        input_str = self.current_input_string
        if not self.automato.start_state: messagebox.showwarning("Simulação", "Defina estado inicial.", parent=self.root); return
        
        self.history, _ = self.automato.simulate_history(input_str) # Pega o novo histórico
        
        self.sim_step = 0; self.sim_playing = False; self.result_indicator = None
        
        # Garante que history não esteja vazio, mesmo se a simulação falhar no início
        if not self.history:
             start_stack = (self.automato.start_stack_symbol,)
             start_state = self.automato.start_state if self.automato.start_state else "-"
             self.history = [(start_state, 0, start_stack)]

        self.draw_all(); self.status.config(f"Simulação iniciada para '{input_str}'.")
    # ***** FIM DA MODIFICAÇÃO *****

    # ***** INÍCIO DA MODIFICAÇÃO *****
    def cmd_step(self):
        if not self.history: self.status.config(text="Nenhuma simulação ativa."); return
        if self.sim_step < len(self.history) - 1:
            self.sim_step += 1; self.draw_all()
            self.status.config(text=f"Passo {self.sim_step}...")
        else:
            # Re-simula para obter o resultado final (se não foi loop)
            # Usa a string de entrada guardada
            _, accepted = self.automato.simulate_history(self.current_input_string) 
            self.result_indicator = "ACEITA" if accepted else "REJEITADA"
            self.status.config(text="Fim da simulação.")
            self.draw_all()
    # ***** FIM DA MODIFICAÇÃO *****

    def cmd_play_pause(self):
        if not self.history: return
        self.sim_playing = not self.sim_playing
        if self.sim_playing:
            self.status.config(text="Reproduzindo...")
            if self.sim_step >= len(self.history) - 1: self.cmd_start_simulation() # Reinicia se já terminou
            self._playback_step()
        else:
            self.status.config(text="Pausado.")

    # ***** INÍCIO DA MODIFICAÇÃO *****
    def _playback_step(self):
        if self.sim_playing and self.sim_step < len(self.history) - 1:
            self.cmd_step(); self.root.after(ANIM_MS, self._playback_step)
        elif self.sim_playing: # Chegou ao fim durante a reprodução
            self.sim_playing = False
            # Re-simula para obter o resultado final
            _, accepted = self.automato.simulate_history(self.current_input_string)
            self.result_indicator = "ACEITA" if accepted else "REJEITADA"
            self.draw_all() # Desenha o último estado com o resultado
            self.status.config(text="Reprodução finalizada.")
    # ***** FIM DA MODIFICAÇÃO *****

    def cmd_reset_sim(self):
        self.history = []; self.sim_step = 0; self.sim_playing = False; self.result_indicator = None
        self.current_input_string = "" # Limpa a string guardada
        self.draw_all(); self.status.config(text="Simulação reiniciada.")

    # --- Handlers Eventos Canvas ---
    def on_canvas_click(self, event):
        cx, cy = self._to_canvas(event.x, event.y)
        clicked_state = self._find_state_at(cx, cy)
        clicked_edge = self._find_edge_at(cx, cy)

        # --- EXCLUIR TRANSIÇÃO ---
        if self.mode == "delete_transition" or self.pinned_mode == "delete_transition":
            if clicked_edge: self._delete_edge(*clicked_edge); self._set_mode("select", pinned=True)
            else: self.status.config(text="Clique no rótulo de uma transição para excluí-la.")
            return
        # -------------------------

        if self.mode == "add_state" or self.pinned_mode == "add_state":
            s_name = f"q{len(self.automato.states)}"
            self._push_undo_snapshot(); self.automato.add_state(s_name); self.positions[s_name] = (cx, cy); self.draw_all()
            self.status.config(text=f"Estado '{s_name}' adicionado.")
            # Não volta para select, permite adicionar mais
            return

        if (self.mode == "set_start" or self.pinned_mode == "set_start") and clicked_state:
            self._push_undo_snapshot(); self.automato.start_state = clicked_state; self._set_mode("select", pinned=True); self.draw_all()
            self.status.config(text=f"'{clicked_state}' definido como inicial.")
            return

        if (self.mode == "toggle_final" or self.pinned_mode == "toggle_final") and clicked_state:
            self._push_undo_snapshot()
            if clicked_state in self.automato.final_states: self.automato.final_states.remove(clicked_state)
            else: self.automato.final_states.add(clicked_state)
            self._set_mode("select", pinned=True); self.draw_all(); self.status.config(text=f"Estado final '{clicked_state}' alternado.")
            return

        if self.mode == "delete_state" or self.pinned_mode == "delete_state":
            if clicked_state and messagebox.askyesno("Excluir", f"Excluir estado '{clicked_state}'?", parent=self.root):
                self._push_undo_snapshot(); self.automato.remove_state(clicked_state)
                if clicked_state in self.positions: del self.positions[clicked_state]
                self._set_mode("select", pinned=True); self.draw_all(); self.status.config(text=f"Estado '{clicked_state}' excluído.")
            return

        if (self.mode == "add_transition_src" or self.pinned_mode == "add_transition_src") and clicked_state:
            self.transition_src = clicked_state; self._set_mode("add_transition_dst", pinned=True)
            self.status.config(text=f"Origem {clicked_state}. Clique no destino.")
            return

        if (self.mode == "add_transition_dst" or self.pinned_mode == "add_transition_dst") and clicked_state:
            src, dst = self.transition_src, clicked_state
            
            # --- USA O DIÁLOGO CUSTOMIZADO ---
            label = self._ask_custom_string(
                "Transição de Pilha",
                f"Formato: 'entrada, desempilha / empilha' (de {src} para {dst})\n(Use & ou ε para vazio, ex: aa,a/ba)"
            )

            if label:
                try:
                    read_part, push_part = label.split('/', 1)
                    parts = read_part.split(',', 1)
                    input_sym = parts[0].strip(); pop_sym = parts[1].strip() if len(parts) > 1 else EPSILON
                    # Trata ε e & como EPSILON, string vazia também como EPSILON
                    # IMPORTANTE: Não removemos mais 'aa' aqui, permitimos símbolos multi-caractere
                    input_final = (input_sym.replace('ε', EPSILON) or EPSILON) if input_sym else EPSILON
                    pop_final = (pop_sym.replace('ε', EPSILON) or EPSILON) if pop_sym else EPSILON
                    # Para push, ε significa não empilhar nada (string vazia)
                    # mas se a string for não-vazia, tratamos ε dentro dela como EPSILON literal? Não, vamos remover.
                    # String vazia após strip() vira EPSILON
                    push_raw = push_part.strip().replace('ε', '') # Remove epsilon do push se houver (ex: aεb -> ab)
                    push_final = push_raw if push_raw else EPSILON # Se ficou vazio, é EPSILON

                    self._push_undo_snapshot(); self.automato.add_transition(src, input_final, pop_final, dst, push_final); self.draw_all()
                    self.status.config(text=f"Transição {src} -> {dst} adicionada.")
                except (ValueError, IndexError) as e: messagebox.showerror("Erro Formato", f"Formato inválido. Use 'entrada, desempilha / empilha'.\nDetalhe: {e}", parent=self.root)
            else: self.status.config(text="Adição cancelada.")
            self._set_mode("select", pinned=True); self.transition_src = None
            return

        # Modo select ou clique no vazio
        if clicked_state: self.dragging = (clicked_state, cx, cy) # Inicia arrasto
        else: self.dragging = None # Cancela arrasto

    def on_canvas_drag(self, event):
        if self.dragging:
            sid, ox, oy = self.dragging; cx, cy = self._to_canvas(event.x, event.y)
            dx, dy = cx - ox, cy - oy; x0, y0 = self.positions.get(sid, (cx, cy))
            self.positions[sid] = (x0 + dx, y0 + dy); self.dragging = (sid, cx, cy); self.draw_all()

    def on_canvas_release(self, event):
        if self.dragging: self._push_undo_snapshot() # Salva posição após arrastar
        self.dragging = None

    def on_right_click(self, event):
        cx, cy = self._to_canvas(event.x, event.y)
        state = self._find_state_at(cx, cy)
        if state: self._show_state_context_menu(event, state); return
        edge = self._find_edge_at(cx, cy)
        if edge: self._show_edge_context_menu(event, *edge)

    def on_canvas_double_click(self, event):
        cx, cy = self._to_canvas(event.x, event.y)
        edge = self._find_edge_at(cx, cy)
        if edge: self._edit_edge(*edge)

    # --- Menus Contexto ---
    def _show_state_context_menu(self, event, state):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Definir como inicial", command=lambda s=state: self._set_start_from_menu(s))
        menu.add_command(label="Alternar final", command=lambda s=state: self._toggle_final_from_menu(s))
        menu.add_command(label="Renomear", command=lambda s=state: self._rename_state_from_menu(s))
        menu.add_separator()
        menu.add_command(label="Excluir", command=lambda s=state: self._delete_state_from_menu(s))
        menu.tk_popup(event.x_root, event.y_root)

    def _show_edge_context_menu(self, event, src, dst):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Editar transições...", command=lambda s=src, d=dst: self._edit_edge(s, d))
        menu.add_separator()
        # --- NOVO ITEM MENU ---
        menu.add_command(label="Excluir todas as transições", command=lambda s=src, d=dst: self._delete_edge(s, d))
        # ----------------------
        menu.tk_popup(event.x_root, event.y_root)

    # --- Ações Menu Contexto ---
    def _set_start_from_menu(self, state): self._push_undo_snapshot(); self.automato.start_state = state; self.draw_all(); self.status.config(text=f"'{state}' é inicial.")
    def _toggle_final_from_menu(self, state):
        self._push_undo_snapshot()
        if state in self.automato.final_states: self.automato.final_states.remove(state)
        else: self.automato.final_states.add(state)
        self.draw_all(); self.status.config(text=f"Estado final '{state}' alternado.")

    def _delete_state_from_menu(self, state):
        if messagebox.askyesno("Excluir", f"Excluir estado '{state}'?", parent=self.root):
            self._push_undo_snapshot(); self.automato.remove_state(state)
            if state in self.positions: del self.positions[state]
            self.draw_all(); self.status.config(text=f"Estado '{state}' excluído.")

    def _rename_state_from_menu(self, old_name: str):
        # --- USA O DIÁLOGO CUSTOMIZADO ---
        new_name = self._ask_custom_string(
            "Renomear",
            f"Novo nome para '{old_name}':",
            initial_value=old_name
        )
        
        if new_name and new_name != old_name:
            try:
                self._push_undo_snapshot(); self.automato.rename_state(old_name, new_name)
                self.positions[new_name] = self.positions.pop(old_name); self.draw_all()
                self.status.config(text=f"'{old_name}' renomeado para '{new_name}'.")
            except ValueError as e: messagebox.showerror("Erro", str(e), parent=self.root); self.undo()

    # --- NOVO MÉTODO ---
    def _delete_edge(self, src, dst):
        """Exclui TODAS as transições entre src e dst."""
        if messagebox.askyesno("Excluir Transições", f"Excluir TODAS as transições de '{src}' para '{dst}'?", parent=self.root):
            modified = False
            transitions_to_remove = [] # Lista de (inp, pop, push)
            
            # Encontra todas as transições de src para dst
            for (s_key, inp, pop), destinations in self.automato.transitions.items():
                if s_key == src:
                    for d_state, push in destinations:
                        if d_state == dst:
                            transitions_to_remove.append((inp, pop, d_state, push))
                            modified = True
            
            if modified:
                self._push_undo_snapshot()
                # Remove as transições encontradas
                for inp, pop, d_state, push in transitions_to_remove:
                    self.automato.remove_pda_transition(src, inp, pop, d_state, push)
                    
                self.draw_all()
                self.status.config(text=f"Transições de {src} para {dst} excluídas.")
            else:
                self.status.config(text="Nenhuma transição encontrada.")
    # ------------------

    def _edit_edge(self, src: str, dst: str):
        """ Edita TODAS as transições entre src e dst usando um diálogo. """
        current_labels = []
        transitions_to_remove = [] # Guarda as transições originais para remover depois
        # Coleta todas as transições existentes de src para dst
        for (s, inp, pop), destinations in self.automato.transitions.items():
            if s == src:
                for d_state, push in destinations:
                    if d_state == dst:
                        inp_disp = inp.replace(EPSILON, "ε") or "ε"
                        pop_disp = pop.replace(EPSILON, "ε") or "ε"
                        push_disp = push.replace(EPSILON, "ε") or "ε"
                        current_labels.append(f"{inp_disp},{pop_disp}/{push_disp}")
                        transitions_to_remove.append((inp, pop, push)) # Guarda original
        
        initial_value = "\n".join(sorted(current_labels))

        # Cria diálogo para edição
        dialog = tk.Toplevel(self.root); dialog.title(f"Editar {src} -> {dst}"); dialog.transient(self.root); dialog.grab_set(); dialog.geometry("400x300")
        
        # --- FONTE AUMENTADA ---
        tk.Label(dialog, text="Transições (uma por linha):\nFormato: 'entrada, desempilha / empilha' (use ε para vazio)", justify="left", font=("Helvetica", 12)).pack(pady=5)
        text_widget = tk.Text(dialog, wrap="word", height=10, width=45, font=("Courier", 12)); text_widget.pack(pady=5, padx=10, expand=True, fill="both"); text_widget.insert("1.0", initial_value)
        # --- FIM DA MUDANÇA ---
        
        new_labels_str = None
        def on_ok(): nonlocal new_labels_str; new_labels_str = text_widget.get("1.0", tk.END).strip(); dialog.destroy()
        def on_cancel(): dialog.destroy()
        btn_frame = tk.Frame(dialog); btn_frame.pack(pady=5); ttk.Button(btn_frame, text="OK", command=on_ok, style="Accent.TButton").pack(side=tk.LEFT, padx=5); ttk.Button(btn_frame, text="Cancelar", command=on_cancel).pack(side=tk.LEFT, padx=5)
        dialog.wait_window()

        if new_labels_str is not None:
            self._push_undo_snapshot()
            
            # Remove antigas transições src -> dst
            for inp, pop, push in transitions_to_remove:
                self.automato.remove_pda_transition(src, inp, pop, dst, push)

            # Adiciona novas transições baseadas no texto editado
            errors = []
            for i, line in enumerate([ln.strip() for ln in new_labels_str.split('\n') if ln.strip()]):
                if '/' in line:
                    try:
                        read_part, push_part = line.split('/', 1)
                        parts = read_part.split(',', 1)
                        inp = parts[0].strip(); pop = parts[1].strip() if len(parts) > 1 else "ε"
                        # Permite multi-caracteres aqui também
                        inp_f = (inp.replace('ε', EPSILON) or EPSILON) if inp else EPSILON
                        pop_f = (pop.replace('ε', EPSILON) or EPSILON) if pop else EPSILON
                        push_raw = push_part.strip().replace('ε', '')
                        push_f = push_raw if push_raw else EPSILON
                        self.automato.add_transition(src, inp_f, pop_f, dst, push_f)
                    except (ValueError, IndexError): errors.append(f"Linha {i+1}: '{line}'")
                elif line: errors.append(f"Linha {i+1}: '{line}' (falta '/')")

            if errors: messagebox.showwarning("Erro Formato", "Ignoradas:\n" + "\n".join(errors), parent=self.root)
            self.draw_all(); self.status.config(text=f"Transições {src}->{dst} atualizadas.")

    # --- Zoom/Pan e Busca ---
    def _to_canvas(self, x, y): return (x - self.offset_x) / self.scale, (y - self.offset_y) / self.scale
    def _from_canvas(self, x, y): return x * self.scale + self.offset_x, y * self.scale + self.offset_y

    def on_mousewheel(self, event):
        delta = event.delta if hasattr(event, "delta") else (120 if event.num==4 else -120)
        factor = 1.0 + (delta / 1200.0); old_scale = self.scale
        self.scale = max(0.2, min(3.0, self.scale * factor))
        mx, my = event.x, event.y; cx_before, cy_before = self._to_canvas(mx, my)
        self.offset_x = mx - cx_before * self.scale; self.offset_y = my - cy_before * self.scale
        self.draw_all()

    def on_middle_press(self, event): self.pan_last = (event.x, event.y)
    def on_middle_release(self, event): self.pan_last = None
    def on_middle_drag(self, event):
        if self.pan_last:
            dx, dy = event.x - self.pan_last[0], event.y - self.pan_last[1]
            self.offset_x += dx; self.offset_y += dy; self.pan_last = (event.x, event.y)
            self.draw_all()

    def _find_state_at(self, cx, cy):
        for sid, (sx, sy) in self.positions.items():
            if math.hypot(cx - sx, cy - sy) <= STATE_RADIUS: return sid # Raio lógico
        return None

    def _find_edge_at(self, cx, cy):
        # Aumenta a tolerância um pouco para facilitar o clique nos rótulos
        min_dist_sq_logic = (25 / self.scale)**2 / (self.scale**2) # Tolerância lógica^2
        found = None; current_min = float('inf')
        for (src, dst), info in self.edge_widgets.items():
            txl, tyl = info.get("text_pos", (None, None))
            if txl is not None:
                d_sq = (cx - txl)**2 + (cy - tyl)**2
                if d_sq < min_dist_sq_logic and d_sq < current_min: found = (src, dst); current_min = d_sq
        return found

    # --- Desenho ---
    def draw_all(self):
        self.canvas.delete("all"); self._draw_simulation_display(); self._draw_edges_and_states()

    # ***** INÍCIO DA MODIFICAÇÃO *****
    def _draw_simulation_display(self):
        """ Desenha pilha e fita no canvas inferior. """
        canvas = self.sim_display_canvas; canvas.delete("all")
        
        try:
             canvas_w = canvas.winfo_width() # Pega largura atual
        except tk.TclError:
             canvas_w = 400 # Valor padrão se a janela não estiver pronta
             
        if not self.history: return
        
        # Pega a configuração do passo atual
        step_idx = min(self.sim_step, len(self.history) - 1)
        _, current_input_idx, stack = self.history[step_idx]

        # Pilha (Stack)
        canvas.create_text(10, 15, text="Pilha:", anchor="nw", font=("Helvetica", 10, "bold"))
        x_p, cell_w, cell_h, base_y = 10, 30, 30, 50
        canvas.create_line(x_p, base_y+1, x_p + 12*cell_w, base_y+1, width=1.5, fill="#555") # Base da pilha
        # Desenha até 12 últimos símbolos da pilha (o topo é o último elemento da tupla)
        stack_draw = list(stack)[-12:]
        for i, sym in enumerate(stack_draw):
            x1 = x_p + i * cell_w
            # Destaca o topo (último elemento)
            fill = "#e0f2fe" if i == len(stack_draw)-1 else "#ffffff" 
            canvas.create_rectangle(x1, base_y - cell_h, x1 + cell_w, base_y, fill=fill, outline="#7dd3fc", width=1)
            canvas.create_text(x1 + cell_w/2, base_y - cell_h/2, text=sym.replace(EPSILON, "ε"), font=("Courier", 12))
        if not stack_draw: canvas.create_text(x_p+cell_w/2, base_y-cell_h/2, text="[vazia]", font=("Courier",10), fill="#888")

        # Fita (Entrada Restante)
        x_f_lbl = x_p + 12*cell_w + 30 # Posição do label da fita
        canvas.create_text(x_f_lbl, 15, text="Entrada Restante:", anchor="nw", font=("Helvetica", 10, "bold"))
        
        # String restante é a partir do índice atual
        remaining_input = self.current_input_string[current_input_idx:]
        input_show = remaining_input or "ε"
        
        x_f = x_f_lbl # Posição inicial da fita
        
        # Cabeça de leitura (triângulo) - aponta para o INÍCIO da fita restante
        canvas.create_polygon(x_f + cell_w/2, base_y - cell_h - 5, x_f + cell_w/2 - 5, base_y - cell_h - 15, x_f + cell_w/2 + 5, base_y - cell_h - 15, fill="black")
        
        # Calcula quantas células da fita cabem no espaço restante
        max_tape_cells = max(1, int((canvas_w - x_f - 10) / cell_w))
        
        # Desenha os próximos símbolos da entrada (limitado pelo espaço)
        for i, sym in enumerate(input_show[:max_tape_cells]):
            x1 = x_f + i * cell_w; fill = "#f1f5f9"
            canvas.create_rectangle(x1, base_y - cell_h, x1 + cell_w, base_y, fill=fill, outline="#cbd5e1")
            canvas.create_text(x1 + cell_w/2, base_y - cell_h/2, text=sym, font=("Courier", 12)) # Mostra caractere literal
            # Não substitui EPSILON aqui, pois ele não deve aparecer na entrada
    # ***** FIM DA MODIFICAÇÃO *****


    # ***** INÍCIO DA MODIFICAÇÃO *****
    def _draw_edges_and_states(self):
        """ Desenha estados e transições no canvas principal. """
        # Pega o estado ativo do passo atual
        active_state = self.history[min(self.sim_step, len(self.history)-1)][0] if self.history else None
        self.edge_widgets.clear() # Limpa posições antigas dos rótulos

        # Agrega transições por (origem, destino)
        agg = defaultdict(list)
        for (src, inp, pop), destinations in self.automato.transitions.items():
            for (dst, push) in destinations:
                inp_d = inp.replace(EPSILON,'ε') or 'ε'
                pop_d = pop.replace(EPSILON,'ε') or 'ε'
                push_d = push.replace(EPSILON,'ε') if push != EPSILON else 'ε' # Mostra ε se push for vazio/EPSILON
                agg[(src, dst)].append(f"{inp_d},{pop_d}/{push_d}")

        rad_logic = STATE_RADIUS # Raio lógico
        rad_view = rad_logic * self.scale # Raio visual

        # Desenha Arestas
        for (src, dst), labels in agg.items():
            if src not in self.positions or dst not in self.positions: continue
            x1l, y1l = self.positions[src]; x2l, y2l = self.positions[dst]
            x1, y1 = self._from_canvas(x1l, y1l); x2, y2 = self._from_canvas(x2l, y2l)
            clr, w = "black", 1.5 * self.scale
            display_labels = sorted(labels)

            if src == dst: # Laço
                # Ajustes para posicionamento do laço e texto
                loop_rx, loop_ry = rad_view*1.2, rad_view*1.6
                cx, cy = x1, y1 - loop_ry*0.8 # Centro superior do laço
                p1=(x1-rad_view*0.5, y1-rad_view*0.8); c1=(cx-loop_rx, cy-loop_ry); c2=(cx+loop_rx, cy-loop_ry); p2=(x1+rad_view*0.5, y1-rad_view*0.8)
                self.canvas.create_line(p1, c1, c2, p2, smooth=True, arrow=tk.LAST, width=w, fill=clr)
                tx, ty = cx, cy - loop_ry*0.9 # Posição do texto acima do laço
                tid = self.canvas.create_text(tx, ty, text="\n".join(display_labels), fill=clr, justify=tk.CENTER, font=("Helvetica", 11)) # <-- Fonte rótulo
                txl, tyl = self._to_canvas(tx, ty); self.edge_widgets[(src, dst)] = {"text_pos": (txl, tyl)}
                self.canvas.tag_bind(tid, "<Double-Button-1>", lambda e, s=src, d=dst: self._edit_edge(s, d))
            else: # Normal
                dx, dy = x2 - x1, y2 - y1; dist = math.hypot(dx, dy) or 1; ux, uy = dx/dist, dy/dist
                bend = 0.25 if (dst, src) in agg else 0 # Curvatura se houver seta de volta
                # Pontos inicial e final na borda dos círculos
                sx, sy = x1+ux*rad_view, y1+uy*rad_view; ex, ey = x2-ux*rad_view, y2-uy*rad_view
                # Ponto de controle da curva
                mx, my = (sx + ex)/2, (sy + ey)/2; cx_ctrl, cy_ctrl = mx - uy*dist*bend, my + ux*dist*bend
                # Posição do texto perto do ponto de controle
                txt_off = 15; tx, ty = cx_ctrl - uy * txt_off, cy_ctrl + ux * txt_off
                self.canvas.create_line(sx, sy, cx_ctrl, cy_ctrl, ex, ey, smooth=True, arrow=tk.LAST, width=w, fill=clr)
                tid = self.canvas.create_text(tx, ty, text="\n".join(display_labels), fill=clr, justify=tk.CENTER, font=("Helvetica", 11)) # <-- Fonte rótulo
                txl, tyl = self._to_canvas(tx, ty); self.edge_widgets[(src, dst)] = {"text_pos": (txl, tyl)}
                self.canvas.tag_bind(tid, "<Double-Button-1>", lambda e, s=src, d=dst: self._edit_edge(s, d))

        # Desenha Estados
        for sid in sorted(self.automato.states):
            if sid not in self.positions: continue
            xl, yl = self.positions[sid]; x, y = self._from_canvas(xl, yl)
            is_start=(sid==self.automato.start_state); is_final=(sid in self.automato.final_states); is_active=(sid==active_state)
            fill, outl, wd = ("#e0f2fe", "#0284c7", 3) if is_active else ("white", "black", 2) # Destaque se ativo
            self.canvas.create_oval(x-rad_view, y-rad_view, x+rad_view, y+rad_view, fill=fill, outline=outl, width=wd)
            if is_final: # Círculo interno para estado final
                self.canvas.create_oval(x-(rad_view-4), y-(rad_view-4), x+(rad_view-4), y+(rad_view-4), outline="black", width=1)
            self.canvas.create_text(x, y, text=sid, font=FONT) # Usa a constante FONT
            if is_start: # Seta inicial
                self.canvas.create_line(x-rad_view*2, y, x-rad_view, y, arrow=tk.LAST, width=2)

        # Indicador Resultado da Simulação
        if self.result_indicator:
            clr = "#16a34a" if self.result_indicator == "ACEITA" else "#dc2626" # Verde ou Vermelho
            try:
                 canvas_width = self.canvas.winfo_width()
                 self.canvas.create_text(canvas_width - 10, 20, text=self.result_indicator, font=("Helvetica", 16, "bold"), fill=clr, anchor="ne")
            except tk.TclError:
                 pass # Ignora se canvas não estiver pronto
    # ***** FIM DA MODIFICAÇÃO *****


    # --- Métodos Undo/Redo ---
    def _push_undo_snapshot(self):
        snap = snapshot_of_pda(self.automato, self.positions)
        if not self.undo_stack or self.undo_stack[-1] != snap:
            self.undo_stack.append(snap)
            if len(self.undo_stack) > 50: self.undo_stack.pop(0)
            self.redo_stack.clear()

    def undo(self, event=None):
        if len(self.undo_stack) > 1:
            self.redo_stack.append(self.undo_stack.pop())
            self.automato, self.positions = restore_from_pda_snapshot(self.undo_stack[-1])
            self.draw_all(); self.status.config(text="Desfeito.")
        else: self.status.config(text="Nada para desfazer.")

    def redo(self, event=None):
        if self.redo_stack:
            snap = self.redo_stack.pop()
            self.undo_stack.append(snap)
            self.automato, self.positions = restore_from_pda_snapshot(snap)
            self.draw_all(); self.status.config(text="Refeito.")
        else: self.status.config(text="Nada para refazer.")