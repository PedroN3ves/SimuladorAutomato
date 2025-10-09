#!/usr/bin/env python3
"""
gui.py - Interface Tkinter para editar e simular autômatos.
"""
import json
import math
import io
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox, ttk
from typing import Dict, Tuple, Set, List, DefaultDict, Optional

from automato import Automato, EPSILON

STATE_RADIUS = 24
FONT = ("Helvetica", 11)
TOKEN_RADIUS = 8
ANIM_MS = 300
 
# Cores
ACTIVE_MODE_COLOR = "#dbeafe"
DEFAULT_BTN_COLOR = "SystemButtonFace"
ACTIVE_TRANSITION_COLOR = "#16a34a" 
DEFAULT_TRANSITION_COLOR = "black"
# --- NOVAS CORES PARA A FITA ---
TAPE_CELL_COLOR = "#f8fafc" # Fundo da célula da fita
TAPE_HEAD_COLOR = "#fef08a" # Fundo da célula ativa (cabeça de leitura)
TAPE_BORDER_COLOR = "#9ca3af" # Borda da fita
# --- NOVA COR PARA O CÍRCULO DO ESTADO ATIVO ---
TAPE_STATE_ACTIVE_COLOR = "#a7f3d0" # Verde claro


# -------------------------
# Utilitários para snapshot (undo/redo)
# -------------------------
def snapshot_of(automato: Automato, positions: Dict[str, Tuple[int, int]]):
    """Retorna JSON serializável representando o estado completo (automato + posições)."""
    data = {
        "automato": json.loads(automato.to_json()),
        "positions": positions
    }
    return json.dumps(data, ensure_ascii=False)

def restore_from_snapshot(s: str):
    data = json.loads(s)
    a = Automato.from_json(json.dumps(data.get("automato", {})))
    pos = data.get("positions", {})
    return a, pos

# -------------------------
# Editor GUI
# -------------------------
class EditorGUI:
    def __init__(self, root: tk.Toplevel):
        self.root = root
        root.title("IC-Tômato++ — Editor de Autômatos")
        root.state('zoomed') # Inicia a janela maximizada

        # Estilo para aumentar o tamanho dos botões
        style = ttk.Style()
        style.configure("TButton", padding=(10, 5))
        style.configure("Accent.TButton", padding=(10, 5))
        style.configure("TMenubutton", padding=(10, 5))

        # Modelo de dados
        self.automato = Automato()
        self.positions: Dict[str, Tuple[int, int]] = {}
        self.state_widgets: Dict[str, Dict] = {}
        self.edge_widgets: Dict[Tuple[str, str], Dict] = {}
        self.selected_state = None
        self.dragging = None
        self.mode = "select"
        self.transition_src = None
        
        self.mode_buttons: Dict[str, tk.Button] = {}

        # Undo/Redo
        self.undo_stack: List[str] = []
        self.redo_stack: List[str] = []

        # Simulação
        self.history: List[Set[str]] = []
        self.sim_step = 0
        self.sim_playing = False
        self.sim_input_str = ""
        self.result_indicator = None

        # Transform (zoom/pan)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_last = None
        self.current_filepath = None

        # Construção da UI
        self._build_toolbar()
        self._build_canvas()
        self._build_bottom()
        self._build_statusbar()
        self._bind_events()

        # Adiciona um pequeno atraso para garantir que a janela tenha as dimensões corretas
        self.root.after(100, self.center_view)

        self.draw_all()
        self._push_undo_snapshot()
        self._update_mode_button_styles()

    def center_view(self):
        """Centraliza a visualização do autômato no canvas."""
        if not self.positions:
            # Se não houver estados, centraliza a visualização em um ponto padrão
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            self.offset_x = canvas_width / 2 - (100 * self.scale)
            self.offset_y = canvas_height / 2 - (100 * self.scale)
            self.draw_all()
            return

        # Esta função pode ser expandida para um "zoom to fit" no futuro,
        # mas por enquanto, centralizar já melhora muito a experiência inicial.
        # A lógica de zoom/pan do usuário continua funcionando normalmente.
        pass

    # -------------------------
    # Construção UI
    # -------------------------
    def _build_toolbar(self):
        toolbar = tk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5, 10))

        # --- Menu Arquivo ---
        file_menu_button = ttk.Menubutton(toolbar, text="Arquivo")
        file_menu = tk.Menu(file_menu_button, tearoff=0)
        file_menu.add_command(label="Abrir...", command=self.cmd_open)
        file_menu.add_command(label="Salvar", command=self.cmd_save)
        file_menu.add_command(label="Salvar Como...", command=self.cmd_save_as)
        file_menu_button["menu"] = file_menu
        file_menu_button.pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient='vertical').pack(side=tk.LEFT, padx=8, fill='y')

        # Grupo 1: Edição
        self.mode_buttons["add_state"] = ttk.Button(toolbar, text="Novo Estado", command=self.cmd_add_state)
        self.mode_buttons["add_state"].pack(side=tk.LEFT, padx=2)
        self.mode_buttons["add_transition"] = ttk.Button(toolbar, text="Nova Transição", command=self.cmd_add_transition)
        self.mode_buttons["add_transition"].pack(side=tk.LEFT, padx=2)
        self.mode_buttons["set_start"] = ttk.Button(toolbar, text="Definir Início", command=self.cmd_set_start)
        self.mode_buttons["set_start"].pack(side=tk.LEFT, padx=2)
        self.mode_buttons["toggle_final"] = ttk.Button(toolbar, text="Alternar Final", command=self.cmd_toggle_final)
        self.mode_buttons["toggle_final"].pack(side=tk.LEFT, padx=2)
        self.mode_buttons["delete_state"] = ttk.Button(toolbar, text="Excluir Estado", command=self.cmd_delete_state_mode)
        self.mode_buttons["delete_state"].pack(side=tk.LEFT, padx=2)
        self.mode_buttons["delete_transition"] = ttk.Button(toolbar, text="Excluir Transição", command=self.cmd_delete_transition_mode)
        self.mode_buttons["delete_transition"].pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient='vertical').pack(side=tk.LEFT, padx=8, fill='y')

        # Grupo 2: Operações e Simulação
        operations_menu_button = ttk.Menubutton(toolbar, text="Operações")
        operations_menu = tk.Menu(operations_menu_button, tearoff=0)
        operations_menu.add_command(label="Converter AFND → AFD", command=self.cmd_convert_to_dfa)
        operations_menu.add_command(label="Minimizar AFD", command=self.cmd_minimize)
        operations_menu.add_command(label="Validar AFD", command=self.cmd_validate_dfa)
        operations_menu.add_separator()
        operations_menu.add_command(label="Converter para Gramática Regular", command=self.cmd_convert_to_grammar)
        operations_menu.add_separator()
        operations_menu.add_command(label="Simulação Rápida", command=self.cmd_quick_simulate)
        operations_menu_button["menu"] = operations_menu
        operations_menu_button.pack(side=tk.LEFT, padx=2)

        # Grupo 3: Exportação
        export_menu_button = ttk.Menubutton(toolbar, text="Exportar")
        export_menu = tk.Menu(export_menu_button, tearoff=0)
        export_menu.add_command(label="Exportar para TikZ (.tex)", command=self.cmd_export_tikz)
        export_menu.add_command(label="Exportar para SVG (.svg)", command=self.cmd_export_svg)
        export_menu.add_command(label="Exportar para PNG (.png)", command=self.cmd_export_png)
        export_menu_button["menu"] = export_menu
        export_menu_button.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient='vertical').pack(side=tk.LEFT, padx=8, fill='y')

        # Grupo 4: Desfazer/Refazer
        ttk.Button(toolbar, text="Undo (Ctrl+Z)", command=self.undo).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Redo (Ctrl+Y)", command=self.redo).pack(side=tk.LEFT, padx=2)

        self.mode_label = ttk.Label(toolbar, text="Modo: selecionar")
        self.mode_label.pack(side=tk.RIGHT)

    def _build_canvas(self):
        self.canvas = tk.Canvas(self.root, width=1100, height=700, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=0)

    def _build_bottom(self):
        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Label(bottom, text="Entrada para Simulação:").pack(side=tk.LEFT)
        self.input_entry = ttk.Entry(bottom, width=30)
        self.input_entry.pack(side=tk.LEFT, padx=6)
        ttk.Button(bottom, text="Simular", command=self.cmd_simulate, style="Accent.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Passo", command=self.cmd_step).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Play/Pausar", command=self.cmd_play_pause).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Reiniciar", command=self.cmd_reset_sim).pack(side=tk.LEFT, padx=2)
        ttk.Separator(bottom, orient='vertical').pack(side=tk.LEFT, padx=8, fill='y')
        ttk.Button(bottom, text="Testar Múltiplas Entradas", command=self.cmd_batch_test).pack(side=tk.LEFT, padx=2)

    def _build_statusbar(self):
        self.status = tk.Label(self.root, text="Pronto", anchor="w", relief=tk.SUNKEN)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)
        
    def _bind_events(self):
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel)
        self.canvas.bind("<Button-5>", self.on_mousewheel)
        self.canvas.bind("<Button-2>", self.on_middle_press)
        self.canvas.bind("<B2-Motion>", self.on_middle_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_middle_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())

    def _update_mode_button_styles(self):
        """Atualiza o estilo dos botões de modo para refletir o modo atual."""
        for mode_name, button in self.mode_buttons.items():
            current_base_mode = self.mode.replace("_src", "").replace("_dst", "")
            
            if mode_name == current_base_mode:
                button.config(style="Accent.TButton") # Estilo de destaque para o botão ativo
            else:
                button.config(style="TButton") # Estilo padrão
    
    def _set_mode(self, new_mode):
        """Define um novo modo de operação e atualiza a UI."""
        self.mode = new_mode
        
        mode_text_map = {
            "select": "Modo: Selecionar",
            "add_state": "Modo: Adicionar Estado",
            "add_transition_src": "Modo: Adicionar Transição (Origem)",
            "add_transition_dst": "Modo: Adicionar Transição (Destino)",
            "set_start": "Modo: Definir Início",
            "toggle_final": "Modo: Alternar Final",
            "delete_state": "Modo: Excluir Estado",
            "delete_transition": "Modo: Excluir Transição"
        }
        cursor_map = {
            "add_state": "crosshair",
            "add_transition_src": "hand2",
            "add_transition_dst": "hand2",
            "delete_state": "X_cursor",
            "delete_transition": "X_cursor",
            "set_start": "hand2",
            "toggle_final": "hand2",
        }
        self.canvas.config(cursor=cursor_map.get(new_mode, "arrow"))
        self.mode_label.config(text=mode_text_map.get(new_mode, "Modo: Selecionar"))
        self._update_mode_button_styles()

    def cmd_add_state(self):
        self._set_mode("add_state")
        self.status.config(text="Clique no canvas para posicionar o novo estado.")

    def cmd_add_transition(self):
        self._set_mode("add_transition_src")
        self.transition_src = None
        self.status.config(text="Clique no estado de origem.")

    def cmd_set_start(self):
        self._set_mode("set_start")
        self.status.config(text="Clique em um estado para torná-lo inicial.")

    def cmd_toggle_final(self):
        self._set_mode("toggle_final")
        self.status.config(text="Clique em um estado para alternar seu status de final.")

    def cmd_delete_state_mode(self):
        self._set_mode("delete_state")
        self.status.config(text="Clique em um estado para excluí-lo.")

    def cmd_delete_transition_mode(self):
        self._set_mode("delete_transition")
        self.status.config(text="Clique no rótulo de uma transição para excluí-la.")

    def cmd_open(self):
        """Abre um arquivo de autômato (.json)."""
        path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("IC-Tômato++ Files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                snapshot = f.read()
            self.automato, self.positions = restore_from_snapshot(snapshot)
            self.current_filepath = path
            self.root.title(f"IC-Tômato++ — {self.current_filepath}")
            self.undo_stack = [snapshot] # Reseta o histórico de undo/redo
            self.redo_stack.clear()
            self.draw_all()
            self.status.config(text=f"Arquivo '{path}' carregado com sucesso.")
        except Exception as e:
            messagebox.showerror("Erro ao Abrir", f"Não foi possível carregar o arquivo:\n{e}", parent=self.root)

    def cmd_save(self):
        """Salva o autômato no arquivo atual. Se não houver, chama 'Salvar Como'."""
        if not self.current_filepath:
            self.cmd_save_as()
        else:
            try:
                with open(self.current_filepath, "w", encoding="utf-8") as f:
                    f.write(snapshot_of(self.automato, self.positions))
                self.status.config(text=f"Arquivo salvo em '{self.current_filepath}'.")
            except Exception as e:
                messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo:\n{e}", parent=self.root)

    def cmd_save_as(self):
        """Abre um diálogo para salvar o autômato em um novo arquivo."""
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("IC-Tômato++ Files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        self.current_filepath = path
        self.cmd_save()

    def cmd_convert_to_dfa(self):
        if not self.automato.start_state:
            messagebox.showwarning("Converter", "Defina o estado inicial antes de converter.", parent=self.root)
            return
        dfa = self.automato.to_dfa()
        if not dfa:
            messagebox.showerror("Converter", "Falha ao converter para AFD.", parent=self.root)
            return
        self._push_undo_snapshot()
        self.automato = dfa
        self._reposition_states()
        self.draw_all()
        self.status.config(text="Conversão para AFD realizada com sucesso.")

    def cmd_minimize(self):
        try:
            new = self.automato.minimize()
            self._push_undo_snapshot()
            self.automato = new
            self._reposition_states()
            self.draw_all()
            self.status.config(text="AFD minimizado com sucesso.")
        except Exception as e:
            messagebox.showerror("Minimizar", f"Erro ao minimizar: {e}", parent=self.root)

    def cmd_validate_dfa(self):
        ok = self.automato.is_dfa()
        if ok:
            messagebox.showinfo("Validação AFD", "O autômato é um AFD válido.", parent=self.root)
        else:
            messagebox.showwarning("Validação AFD", "O autômato NÃO é um AFD válido (pode ter ε-transições ou não-determinismo).", parent=self.root)
        self.status.config(text=f"Validação AFD: {'OK' if ok else 'Inválido'}")

    def cmd_convert_to_grammar(self):
        """Converte o autômato para uma gramática regular e a exibe."""
        if not self.automato.start_state:
            messagebox.showwarning("Converter para Gramática", "Defina o estado inicial antes de converter.", parent=self.root)
            return

        grammar_str = self.automato.to_regular_grammar()

        # Cria uma nova janela para exibir a gramática
        grammar_window = tk.Toplevel(self.root)
        grammar_window.title("Gramática Regular Gerada")
        grammar_window.geometry("450x400")

        text_area = tk.Text(grammar_window, wrap="word", font=("Courier", 12), relief=tk.FLAT, padx=10, pady=10)
        text_area.pack(expand=True, fill="both")
        text_area.insert("1.0", grammar_str)
        text_area.config(state="disabled") # Torna o texto somente leitura
        grammar_window.transient(self.root) # Mantém a janela no topo
        
    def cmd_quick_simulate(self):
        if not self.automato.states:
            messagebox.showwarning("Simulação Rápida", "O autômato está vazio. Adicione estados primeiro.", parent=self.root)
            return
        if not self.automato.start_state:
            messagebox.showwarning("Simulação Rápida", "O autômato não possui um estado inicial definido.", parent=self.root)
            return
        input_string = simpledialog.askstring("Simulação Rápida",
                                              "Digite a cadeia de entrada (deixe em branco para cadeia vazia ε):",
                                              parent=self.root)
        if input_string is None:
            self.status.config(text="Simulação rápida cancelada.")
            return
        accepted = self.automato.simulate(input_string)
        result_text = "ACEITA" if accepted else "REJEITADA"
        display_string = "ε" if input_string == "" else input_string
        messagebox.showinfo("Resultado da Simulação", f"A cadeia '{display_string}' foi {result_text}.", parent=self.root)
        self.status.config(text=f"Simulação Rápida: '{display_string}' -> {result_text}")

    def cmd_export_tikz(self):
        path = filedialog.asksaveasfilename(defaultextension=".tex", filetypes=[("TeX files", "*.tex")])
        if path:
            with open(path, "w", encoding="utf-8") as f: f.write(self.automato.export_tikz())
            messagebox.showinfo("Exportar", f"TikZ exportado para {path}", parent=self.root)

    def cmd_export_svg(self):
        path = filedialog.asksaveasfilename(defaultextension=".svg", filetypes=[("SVG files", "*.svg")])
        if path:
            with open(path, "w", encoding="utf-8") as f: f.write(self._generate_svg_text())
            messagebox.showinfo("Exportar", f"SVG exportado para {path}", parent=self.root)

    def cmd_export_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
        if not path: return
        svg_text = self._generate_svg_text()
        try:
            import cairosvg
            cairosvg.svg2png(bytestring=svg_text.encode('utf-8'), write_to=path)
            messagebox.showinfo("Exportar PNG", f"PNG salvo em {path}", parent=self.root)
        except ImportError:
            messagebox.showwarning("Exportar PNG", "A biblioteca 'cairosvg' não está instalada.\nPara exportar para PNG, instale com: pip install cairosvg", parent=self.root)
        except Exception as e:
            messagebox.showerror("Exportar PNG", f"Ocorreu um erro: {e}", parent=self.root)

    def _to_canvas(self, x, y):
        return (x - self.offset_x) / self.scale, (y - self.offset_y) / self.scale

    def _from_canvas(self, x, y):
        return x * self.scale + self.offset_x, y * self.scale + self.offset_y

    def on_canvas_click(self, event):
        cx, cy = self._to_canvas(event.x, event.y)
        if self.mode == "add_state":
            sid = f"q{len(self.automato.states)}"
            self.automato.add_state(sid)
            self.positions[sid] = (cx, cy)
            self._push_undo_snapshot()
            self._set_mode("select")
            self.status.config(text=f"Estado {sid} adicionado")
            self.draw_all()
            return

        clicked_state = self._find_state_at(cx, cy)
        clicked_edge = self._find_edge_at(cx, cy)
        
        if self.mode == "delete_transition":
            if clicked_edge:
                self._delete_edge(*clicked_edge)
                self._set_mode("select")
            else:
                self.status.config(text="Clique no rótulo de uma transição para excluí-la.")
            return

        if self.mode == "add_transition_src":
            if clicked_state:
                self.transition_src = clicked_state
                self._set_mode("add_transition_dst")
                self.status.config(text=f"Origem {clicked_state} selecionada. Clique no destino.")
            else:
                self.status.config(text="Clique em um estado de origem válido.")
            return

        if self.mode == "add_transition_dst":
            if clicked_state:
                src = self.transition_src
                dst = clicked_state
                sym = simpledialog.askstring("Símbolos", "Símbolos separados por vírgula (use '&' para vazio):", parent=self.root)
                if sym is not None:
                    syms = [s.strip() or EPSILON for s in sym.split(",")]
                    for s in syms: self.automato.add_transition(src, s, dst)
                    self._push_undo_snapshot()
                    self.status.config(text=f"Transições adicionadas: {src} -> {dst} ({', '.join(syms)})")
                else: self.status.config(text="Transição cancelada.")
                self._set_mode("select")
                self.transition_src = None
                self.draw_all()
            else: self.status.config(text="Clique em um estado de destino.")
            return

        if self.mode == "set_start":
            if clicked_state:
                self._push_undo_snapshot()
                self.automato.start_state = clicked_state
                self._set_mode("select")
                self.status.config(text=f"Estado {clicked_state} definido como inicial.")
                self.draw_all()
            return

        if self.mode == "toggle_final":
            if clicked_state:
                self._push_undo_snapshot()
                if clicked_state in self.automato.final_states: self.automato.final_states.remove(clicked_state)
                else: self.automato.final_states.add(clicked_state)
                self._set_mode("select")
                self.status.config(text=f"Estado final alternado: {clicked_state}")
                self.draw_all()
            return

        if self.mode == "delete_state":
            if clicked_state:
                if messagebox.askyesno("Excluir", f"Excluir estado {clicked_state}?", parent=self.root):
                    self._push_undo_snapshot()
                    self.automato.remove_state(clicked_state)
                    if clicked_state in self.positions: del self.positions[clicked_state]
                    self._set_mode("select")
                    self.status.config(text=f"Estado {clicked_state} excluído.")
                    self.draw_all()
            return

        if clicked_state:
            self.selected_state = clicked_state
            self.dragging = (clicked_state, cx, cy)
            self.status.config(text=f"Selecionado {clicked_state}. Arraste para mover.")
        else: self.selected_state = None

    def on_canvas_drag(self, event):
        if self.dragging:
            sid, ox, oy = self.dragging
            cx, cy = self._to_canvas(event.x, event.y)
            dx, dy = cx - ox, cy - oy
            x0, y0 = self.positions.get(sid, (0, 0))
            self.positions[sid] = (x0 + dx, y0 + dy)
            self.dragging = (sid, cx, cy)
            self.draw_all()

    def on_canvas_release(self, event):
        if self.dragging: self._push_undo_snapshot()
        self.dragging = None

    def on_mousewheel(self, event):
        delta = event.delta if hasattr(event, "delta") else (120 if event.num == 4 else -120)
        factor = 1.0 + (delta / 1200.0)
        old_scale, self.scale = self.scale, max(0.2, min(3.0, self.scale * factor))
        mx, my = event.x, event.y
        cx_before, cy_before = (mx - self.offset_x) / old_scale, (my - self.offset_y) / old_scale
        self.offset_x, self.offset_y = mx - cx_before * self.scale, my - cy_before * self.scale
        self.draw_all()

    def on_middle_press(self, event): self.pan_last = (event.x, event.y)
    def on_middle_release(self, event): self.pan_last = None
    def on_middle_drag(self, event):
        if self.pan_last:
            dx, dy = event.x - self.pan_last[0], event.y - self.pan_last[1]
            self.offset_x += dx; self.offset_y += dy
            self.pan_last = (event.x, event.y)
            self.draw_all()

    def on_right_click(self, event):
        cx, cy = self._to_canvas(event.x, event.y)
        edge = self._find_edge_at(cx, cy)
        if edge: self._show_edge_context_menu(event, *edge); return
        state = self._find_state_at(cx, cy)
        if state: self._show_state_context_menu(event, state)

    def on_canvas_double_click(self, event):
        """Handles double-clicks on the canvas, primarily for editing edges."""
        cx, cy = self._to_canvas(event.x, event.y)
        edge = self._find_edge_at(cx, cy)
        if edge:
            self._edit_edge_label(edge[0], edge[1])

    def _show_state_context_menu(self, tk_event, state):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"Definir como inicial", command=lambda: self._set_start_from_menu(state))
        menu.add_command(label=f"Alternar final", command=lambda: self._toggle_final_from_menu(state))
        menu.add_command(label="Renomear", command=lambda: self._rename_state_from_menu(state))
        menu.add_separator()
        menu.add_command(label="Excluir", command=lambda: self._delete_state_from_menu(state))
        menu.tk_popup(tk_event.x_root, tk_event.y_root)

    def _show_edge_context_menu(self, tk_event, src, dst):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Editar rótulo", command=lambda: self._edit_edge_label(src, dst))
        menu.add_command(label="Excluir transição", command=lambda: self._delete_edge(src, dst))
        menu.tk_popup(tk_event.x_root, tk_event.y_root)

    def _set_start_from_menu(self, state):
        self._push_undo_snapshot(); self.automato.start_state = state; self.draw_all()

    def _toggle_final_from_menu(self, state):
        self._push_undo_snapshot()
        if state in self.automato.final_states: self.automato.final_states.remove(state)
        else: self.automato.final_states.add(state)
        self.draw_all()

    def _delete_state_from_menu(self, state):
        if messagebox.askyesno("Excluir", f"Tem certeza que deseja excluir o estado {state}?", parent=self.root):
            self._push_undo_snapshot()
            self.automato.remove_state(state)
            if state in self.positions: del self.positions[state]
            self.draw_all()

    def _rename_state_from_menu(self, old_name: str):
        """Abre um diálogo para renomear um estado."""
        new_name = simpledialog.askstring("Renomear Estado", f"Digite o novo nome para '{old_name}':",
                                          initialvalue=old_name, parent=self.root)
        
        if new_name and new_name != old_name:
            try:
                self._push_undo_snapshot()
                self.automato.rename_state(old_name, new_name)
                # Atualiza o dicionário de posições
                self.positions[new_name] = self.positions.pop(old_name)
                self.draw_all()
                self.status.config(text=f"Estado '{old_name}' renomeado para '{new_name}'.")
            except ValueError as e:
                messagebox.showerror("Erro ao Renomear", str(e), parent=self.root)
                # Desfaz a alteração no histórico de undo se a operação falhar
                self.undo()

    def _edit_edge_label(self, src, dst):
        cur_label = self.edge_widgets.get((src, dst), {}).get("label", "")
        val = simpledialog.askstring("Editar Rótulo", "Símbolos (separados por vírgula, use '&' para vazio):", initialvalue=cur_label, parent=self.root)
        if val is None: return
        self._push_undo_snapshot()
        # Limpa transições antigas entre esses dois estados
        for sym in cur_label.split(","):
            if sym: self.automato.remove_transition(src, sym, dst)
        # Adiciona as novas
        for sym in (s.strip() or EPSILON for s in val.split(",")):
            if sym: self.automato.add_transition(src, sym, dst)
        self.draw_all()

    def _delete_edge(self, src, dst):
        if messagebox.askyesno("Excluir", f"Excluir todas as transições de {src} para {dst}?", parent=self.root):
            self._push_undo_snapshot()
            cur_label = self.edge_widgets.get((src, dst), {}).get("label", "")
            for sym in cur_label.split(","):
                if sym: self.automato.remove_transition(src, sym, dst)
            self.draw_all()

    def _find_state_at(self, cx, cy):
        for sid, (sx, sy) in self.positions.items():
            if math.hypot(sx - cx, sy - cy) <= STATE_RADIUS: return sid
        return None

    def _find_edge_at(self, cx, cy):
        for (src, dst), info in self.edge_widgets.items():
            tx, ty = info.get("text_pos", (None, None))
            # Aumenta a área de clique para o texto
            if tx and math.hypot(tx-cx, ty-cy) <= 20: return src, dst
        return None
    
    #################################################################
    # NOVA FUNÇÃO PARA DESENHAR A FITA DE ENTRADA                   #
    #################################################################
    def _draw_input_tape(self):
        """Desenha a fita de entrada na parte inferior do canvas durante a simulação."""
        if not self.history:
            return

        cell_width, cell_height = 30, 40
        y_pos = self.canvas.winfo_height() - 60  # Posição Y da fita

        # Centraliza a fita
        tape_width = len(self.sim_input_str) * cell_width
        start_x = (self.canvas.winfo_width() - tape_width) / 2

        for i, symbol in enumerate(self.sim_input_str):
            x1 = start_x + i * cell_width
            y1 = y_pos
            x2 = x1 + cell_width
            y2 = y1 + cell_height

            # Determina se esta é a célula ativa
            is_head = (self.sim_step > 0 and i == self.sim_step - 1)
            fill_color = TAPE_HEAD_COLOR if is_head else TAPE_CELL_COLOR
            
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill_color, outline=TAPE_BORDER_COLOR)
            self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=symbol, font=("Courier", 14, "bold"))
            
            # Desenha a "cabeça de leitura" (um triângulo) acima da célula ativa
            if is_head:
                head_x = (x1 + x2) / 2
                self.canvas.create_polygon(
                    head_x, y1 - 2,
                    head_x - 6, y1 - 10,
                    head_x + 6, y1 - 10,
                    fill=DEFAULT_TRANSITION_COLOR,
                    outline=DEFAULT_TRANSITION_COLOR
                )

    def draw_all(self):
        self.canvas.delete("all")
        self.state_widgets.clear(); self.edge_widgets.clear()
        
        # --- LÓGICA ADICIONADA PARA SIMULAÇÃO ---
        # Pega o conjunto de estados do passo anterior e o atual
        current_active_set = self.history[self.sim_step] if self.history else set()
        prev_active_set = self.history[self.sim_step - 1] if self.history and self.sim_step > 0 else set()
        
        # Pega o símbolo que causou a transição atual
        current_symbol = self.sim_input_str[self.sim_step - 1] if self.sim_input_str and self.sim_step > 0 else None
        # --- FIM DA LÓGICA ADICIONADA ---

        # Agrega transições para desenhar setas múltiplas ou com múltiplos rótulos
        agg: DefaultDict[Tuple[str, str], Set[str]] = DefaultDict(set)
        for (src, sym), dsts in self.automato.transitions.items():
            for dst in dsts: agg[(src, dst)].add(sym)
        
        for (src, dst), syms in agg.items():
            if src not in self.positions or dst not in self.positions: continue
            x1, y1 = self._from_canvas(*self.positions[src])
            x2, y2 = self._from_canvas(*self.positions[dst])
            label = ",".join(sorted(list(syms))).replace(EPSILON, "ε")

            # --- LÓGICA DE DESTAQUE DA TRANSIÇÃO ---
            is_active_transition = False
            # Verifica se a transição foi ativada no passo atual
            if current_symbol and src in prev_active_set and dst in current_active_set:
                 # Checa se o símbolo da transição atual está nos rótulos desta seta
                 if current_symbol in syms:
                     is_active_transition = True
                 if EPSILON in syms:
                     closure_of_prev = self.automato.epsilon_closure(prev_active_set)
                     if src in closure_of_prev and dst in closure_of_prev:
                         is_active_transition = True
            
            color = ACTIVE_TRANSITION_COLOR if is_active_transition else DEFAULT_TRANSITION_COLOR
            width = 3 if is_active_transition else 1.5
            # --- FIM DA LÓGICA DE DESTAQUE ---


            if src == dst:
                r = STATE_RADIUS * self.scale
                p1 = (x1 - r * 0.7, y1 - r * 0.7)
                c1 = (x1 - r * 1.5, y1 - r * 2.5)
                c2 = (x1 + r * 1.5, y1 - r * 2.5)
                p2 = (x1 + r * 0.7, y1 - r * 0.7)
                self.canvas.create_line(p1, c1, c2, p2, smooth=True, arrow=tk.LAST, width=width, fill=color)
                tx, ty = x1, y1 - r * 2.3
                text_id = self.canvas.create_text(tx, ty, text=label, font=FONT, fill=color)
                self.canvas.tag_bind(text_id, "<Double-Button-1>", lambda e, s=src, d=dst: self._edit_edge_label(s, d))

                self.edge_widgets[(src, dst)] = {"label": label, "text_pos": self._to_canvas(tx, ty)}
            else:
                dx, dy = x2 - x1, y2 - y1; dist = math.hypot(dx, dy) or 1
                ux, uy = dx/dist, dy/dist
                offset = 15*self.scale if (dst,src) in agg else 0
                start_x, start_y = x1+ux*STATE_RADIUS*self.scale, y1+uy*STATE_RADIUS*self.scale
                end_x, end_y = x2-ux*STATE_RADIUS*self.scale, y2-uy*STATE_RADIUS*self.scale
                mid_x, mid_y = (start_x+end_x)/2, (start_y+end_y)/2
                ctrl_x, ctrl_y = mid_x - uy*offset, mid_y + ux*offset
                self.canvas.create_line(start_x, start_y, ctrl_x, ctrl_y, end_x, end_y, smooth=True, width=width, arrow=tk.LAST, fill=color)
                txt_x, txt_y = mid_x-uy*(offset+15), mid_y+ux*(offset+15)
                text_id = self.canvas.create_text(txt_x, txt_y, text=label, font=FONT, fill=color)
                self.canvas.tag_bind(text_id, "<Double-Button-1>", lambda e, s=src, d=dst: self._edit_edge_label(s, d))

                self.edge_widgets[(src, dst)] = {"label": label, "text_pos": self._to_canvas(txt_x, txt_y)}

        for sid in sorted(list(self.automato.states)):
            x_logic, y_logic = self.positions.get(sid, (100, 100))
            x, y = self._from_canvas(x_logic, y_logic)
            is_active = sid in current_active_set
            fill, outline, width = ("#e0f2fe", "#0284c7", 3) if is_active else ("white", "black", 2)
            self.canvas.create_oval(x-STATE_RADIUS*self.scale, y-STATE_RADIUS*self.scale, x+STATE_RADIUS*self.scale, y+STATE_RADIUS*self.scale, fill=fill, outline=outline, width=width)
            self.canvas.create_text(x, y, text=sid, font=FONT)
            if sid in self.automato.final_states:
                self.canvas.create_oval(x-(STATE_RADIUS-5)*self.scale, y-(STATE_RADIUS-5)*self.scale, x+(STATE_RADIUS-5)*self.scale, y+(STATE_RADIUS-5)*self.scale, outline="black", width=2)
        
        if self.automato.start_state and self.automato.start_state in self.positions:
            sx, sy = self._from_canvas(*self.positions[self.automato.start_state])
            self.canvas.create_line(sx-STATE_RADIUS*2*self.scale, sy, sx-STATE_RADIUS*self.scale, sy, arrow=tk.LAST, width=2)
        
        if self.result_indicator:
            color = "#16a34a" if self.result_indicator == "ACEITA" else "#dc2626"
            self.canvas.create_text(self.canvas.winfo_width()-60, 30, text=self.result_indicator, font=("Helvetica", 16, "bold"), fill=color)

        # --- CHAMA A FUNÇÃO DA FITA NO FINAL DO DESENHO ---
        self._draw_input_tape()

    def _reposition_states(self):
        self.positions = {}
        x, y = 100, 100
        for i, s in enumerate(sorted(list(self.automato.states))): self.positions[s] = (x + (i%7)*120, y + (i//7)*120)

    def cmd_simulate(self):
        self.sim_input_str = self.input_entry.get()
        history, _ = self.automato.simulate_history(self.sim_input_str)
        if not history: 
            messagebox.showwarning("Simular", "Autômato vazio ou sem estado inicial.", parent=self.root)
            return
        self.history = [h for h, _ in history]
        self.sim_step, self.result_indicator, self.sim_playing = 0, None, False
        self.draw_all()

    def cmd_step(self):
        if not self.history:
            messagebox.showwarning("Passo", "Nenhuma simulação em andamento. Clique em 'Simular' primeiro.", parent=self.root)
            return
            
        if self.sim_step >= len(self.history) - 1:
            if self.history:
                accepted = bool(self.history[-1] & self.automato.final_states)
                self.result_indicator = "ACEITA" if accepted else "REJEITADA"
                self.draw_all()
            return
        self.sim_step += 1
        self.draw_all()

    def cmd_play_pause(self):
        if not self.history: messagebox.showwarning("Play", "Nenhuma simulação em andamento.", parent=self.root); return
        self.sim_playing = not self.sim_playing
        self.status.config(text="Reproduzindo..." if self.sim_playing else "Pausado")
        if self.sim_playing: self._playback_step()

    def _playback_step(self):
        if self.sim_playing and self.sim_step < len(self.history) - 1:
            self.cmd_step();
            self.root.after(ANIM_MS, self._playback_step)
        elif self.sim_playing:
            self.result_indicator = "ACEITA" if bool(self.history[-1] & self.automato.final_states) else "REJEITADA"
            self.sim_playing = False
            self.draw_all()
    
    def cmd_reset_sim(self):
        self.history, self.sim_step, self.sim_playing, self.result_indicator, self.sim_input_str = [], 0, False, None, ""
        self.draw_all()
        self.status.config(text="Simulação reiniciada.")

    def cmd_batch_test(self):
        text = simpledialog.askstring("Testar Múltiplas Entradas", "Palavras separadas por vírgula (ε para vazio):", parent=self.root)
        text = simpledialog.askstring("Testar Múltiplas Entradas", "Palavras separadas por vírgula ('&' para vazio):", parent=self.root)
        if text is None: return
        items = [s.strip() for s in text.split(",")]
        results = [f"'{w}': {'ACEITO' if self.automato.simulate('' if w == '&' else w) else 'REJEITADO'}" for w in items]
        messagebox.showinfo("Resultados dos Testes", "\n".join(results), parent=self.root)

    def _push_undo_snapshot(self):
        snap = snapshot_of(self.automato, self.positions)
        if not self.undo_stack or self.undo_stack[-1] != snap:
            self.undo_stack.append(snap)
            if len(self.undo_stack) > 50: self.undo_stack.pop(0)
            self.redo_stack.clear()

    def undo(self):
        if len(self.undo_stack) > 1:
            self.redo_stack.append(self.undo_stack.pop())
            self.automato, self.positions = restore_from_snapshot(self.undo_stack[-1])
            self.draw_all(); self.status.config(text="Desfeito.")
        else: self.status.config(text="Nada para desfazer.")

    def redo(self):
        if self.redo_stack:
            snap = self.redo_stack.pop()
            self.undo_stack.append(snap)
            self.automato, self.positions = restore_from_snapshot(snap)
            self.draw_all(); self.status.config(text="Refeito.")
        else: self.status.config(text="Nada para refazer.")
            
    def _generate_svg_text(self):
        # Placeholder
        return '<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg"></svg>'
