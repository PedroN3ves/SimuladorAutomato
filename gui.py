#!/usr/bin/env python3
"""
gui.py - Interface Tkinter para editar e simular autômatos.
"""
import json
import math
import io
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
from typing import Dict, Tuple, Set, List, DefaultDict, Optional

from automato import Automato, EPSILON

STATE_RADIUS = 24
FONT = ("Helvetica", 11)
TOKEN_RADIUS = 8
ANIM_MS = 300

# Cores para os botões de modo
ACTIVE_MODE_COLOR = "#dbeafe"  # Azul claro
DEFAULT_BTN_COLOR = "SystemButtonFace" # Cor padrão do sistema

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
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("IC-Tômato++ — Editor de Autômatos")

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
        self.token_items: List[int] = []
        self.result_indicator = None

        # Transform (zoom/pan)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_last = None

        # Construção da UI
        self._build_toolbar()
        self._build_canvas()
        self._build_bottom()
        self._build_statusbar()
        self._bind_events()

        self.draw_all()
        self._push_undo_snapshot()
        self._update_mode_button_styles()

    # -------------------------
    # Construção UI
    # -------------------------
    def _build_toolbar(self):
        toolbar = tk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)

        # Grupo 1: Edição
        self.mode_buttons["add_state"] = tk.Button(toolbar, text="Novo Estado", command=self.cmd_add_state)
        self.mode_buttons["add_state"].pack(side=tk.LEFT)
        
        self.mode_buttons["add_transition"] = tk.Button(toolbar, text="Nova Transição", command=self.cmd_add_transition)
        self.mode_buttons["add_transition"].pack(side=tk.LEFT)
        
        self.mode_buttons["set_start"] = tk.Button(toolbar, text="Definir Início", command=self.cmd_set_start)
        self.mode_buttons["set_start"].pack(side=tk.LEFT)

        self.mode_buttons["toggle_final"] = tk.Button(toolbar, text="Alternar Final", command=self.cmd_toggle_final)
        self.mode_buttons["toggle_final"].pack(side=tk.LEFT)

        self.mode_buttons["delete_state"] = tk.Button(toolbar, text="Excluir Estado", command=self.cmd_delete_state_mode)
        self.mode_buttons["delete_state"].pack(side=tk.LEFT)
        
        self.mode_buttons["delete_transition"] = tk.Button(toolbar, text="Excluir Transição", command=self.cmd_delete_transition_mode)
        self.mode_buttons["delete_transition"].pack(side=tk.LEFT)

        tk.Label(toolbar, text="|").pack(side=tk.LEFT, padx=5)

        # Grupo 2: Operações e Simulação
        tk.Button(toolbar, text="Converter NFA→DFA", command=self.cmd_convert_to_dfa).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Minimizar DFA", command=self.cmd_minimize).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Validar DFA", command=self.cmd_validate_dfa).pack(side=tk.LEFT)
        
        tk.Button(toolbar, text="Simulação Rápida", command=self.cmd_quick_simulate).pack(side=tk.LEFT, padx=2)

        tk.Label(toolbar, text="|").pack(side=tk.LEFT, padx=5)

        # Grupo 3: Exportação
        tk.Button(toolbar, text="Exportar TikZ", command=self.cmd_export_tikz).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Exportar SVG", command=self.cmd_export_svg).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Exportar PNG", command=self.cmd_export_png).pack(side=tk.LEFT)

        tk.Label(toolbar, text="|").pack(side=tk.LEFT, padx=5)

        # Grupo 4: Desfazer/Refazer
        tk.Button(toolbar, text="Undo (Ctrl+Z)", command=self.undo).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Redo (Ctrl+Y)", command=self.redo).pack(side=tk.LEFT)

        self.mode_label = tk.Label(toolbar, text="Modo: selecionar")
        self.mode_label.pack(side=tk.RIGHT)

    def _build_canvas(self):
        self.canvas = tk.Canvas(self.root, width=1100, height=700, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def _build_bottom(self):
        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=6)
        tk.Label(bottom, text="Entrada para Animação:").pack(side=tk.LEFT)
        self.input_entry = tk.Entry(bottom, width=30)
        self.input_entry.pack(side=tk.LEFT, padx=6)
        tk.Button(bottom, text="Animar", command=self.cmd_simulate).pack(side=tk.LEFT)
        tk.Button(bottom, text="Passo", command=self.cmd_step).pack(side=tk.LEFT)
        tk.Button(bottom, text="Play/Pausar", command=self.cmd_play_pause).pack(side=tk.LEFT)
        tk.Button(bottom, text="Reiniciar", command=self.cmd_reset_sim).pack(side=tk.LEFT)
        tk.Label(bottom, text="|").pack(side=tk.LEFT, padx=5)
        tk.Button(bottom, text="Testar Múltiplas Entradas", command=self.cmd_batch_test).pack(side=tk.LEFT)

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
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())

    def _update_mode_button_styles(self):
        """Atualiza a cor de fundo dos botões de modo para refletir o modo atual."""
        for mode_name, button in self.mode_buttons.items():
            current_base_mode = self.mode.replace("_src", "").replace("_dst", "")
            
            if mode_name == current_base_mode:
                button.config(background=ACTIVE_MODE_COLOR, relief=tk.SUNKEN)
            else:
                button.config(background=DEFAULT_BTN_COLOR, relief=tk.RAISED)
    
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
            "delete_transition": "Modo: Excluir Transição",
        }
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

    def cmd_convert_to_dfa(self):
        if not self.automato.start_state:
            messagebox.showwarning("Converter", "Defina o estado inicial antes de converter.")
            return
        dfa = self.automato.to_dfa()
        if not dfa:
            messagebox.showerror("Converter", "Falha ao converter para DFA.")
            return
        self._push_undo_snapshot()
        self.automato = dfa
        self._reposition_states()
        self.draw_all()
        self.status.config(text="Conversão para DFA realizada com sucesso.")

    def cmd_minimize(self):
        try:
            new = self.automato.minimize()
            self._push_undo_snapshot()
            self.automato = new
            self._reposition_states()
            self.draw_all()
            self.status.config(text="DFA minimizado com sucesso.")
        except Exception as e:
            messagebox.showerror("Minimizar", f"Erro ao minimizar: {e}")

    def cmd_validate_dfa(self):
        ok = self.automato.is_dfa()
        if ok:
            messagebox.showinfo("Validação DFA", "O autômato é um DFA válido.")
        else:
            messagebox.showwarning("Validação DFA", "O autômato NÃO é um DFA válido (pode ter ε-transições ou não-determinismo).")
        self.status.config(text=f"Validação DFA: {'OK' if ok else 'Inválido'}")
        
    def cmd_quick_simulate(self):
        if not self.automato.states:
            messagebox.showwarning("Simulação Rápida", "O autômato está vazio. Adicione estados primeiro.")
            return
        if not self.automato.start_state:
            messagebox.showwarning("Simulação Rápida", "O autômato não possui um estado inicial definido.")
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
        messagebox.showinfo("Resultado da Simulação", f"A cadeia '{display_string}' foi {result_text}.")
        self.status.config(text=f"Simulação Rápida: '{display_string}' -> {result_text}")

    def cmd_export_tikz(self):
        path = filedialog.asksaveasfilename(defaultextension=".tex", filetypes=[("TeX files", "*.tex")])
        if path:
            with open(path, "w", encoding="utf-8") as f: f.write(self.automato.export_tikz())
            messagebox.showinfo("Exportar", f"TikZ exportado para {path}")

    def cmd_export_svg(self):
        path = filedialog.asksaveasfilename(defaultextension=".svg", filetypes=[("SVG files", "*.svg")])
        if path:
            with open(path, "w", encoding="utf-8") as f: f.write(self._generate_svg_text())
            messagebox.showinfo("Exportar", f"SVG exportado para {path}")

    def cmd_export_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
        if not path: return
        svg_text = self._generate_svg_text()
        try:
            import cairosvg
            cairosvg.svg2png(bytestring=svg_text.encode('utf-8'), write_to=path)
            messagebox.showinfo("Exportar PNG", f"PNG salvo em {path}")
        except ImportError:
             messagebox.showwarning("Exportar PNG", "A biblioteca 'cairosvg' não está instalada.\nPara exportar para PNG, instale com: pip install cairosvg")
        except Exception as e:
            messagebox.showerror("Exportar PNG", f"Ocorreu um erro: {e}")

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

        if self.mode == "delete_transition":
            edge = self._find_edge_at(cx, cy)
            if edge:
                src, dst = edge
                self._delete_edge(src, dst) 
                self._set_mode("select")
            else:
                self.status.config(text="Nenhuma transição encontrada. Clique em um rótulo.")
            return

        clicked = self._find_state_at(cx, cy)
        if self.mode == "add_transition_src":
            if clicked:
                self.transition_src = clicked
                self._set_mode("add_transition_dst")
                self.status.config(text=f"Origem {clicked} selecionada. Clique no destino.")
            else:
                self.status.config(text="Clique em um estado de origem válido.")
            return

        if self.mode == "add_transition_dst":
            if clicked:
                src = self.transition_src
                dst = clicked
                sym = simpledialog.askstring("Símbolos", "Símbolos separados por vírgula (use 'ε' para épsilon):", parent=self.root)
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
            if clicked:
                self._push_undo_snapshot()
                self.automato.start_state = clicked
                self._set_mode("select")
                self.status.config(text=f"Estado {clicked} definido como inicial.")
                self.draw_all()
            return

        if self.mode == "toggle_final":
            if clicked:
                self._push_undo_snapshot()
                if clicked in self.automato.final_states: self.automato.final_states.remove(clicked)
                else: self.automato.final_states.add(clicked)
                self._set_mode("select")
                self.status.config(text=f"Estado final alternado: {clicked}")
                self.draw_all()
            return

        if self.mode == "delete_state":
            if clicked:
                if messagebox.askyesno("Excluir", f"Excluir estado {clicked}?"):
                    self._push_undo_snapshot()
                    self.automato.remove_state(clicked)
                    if clicked in self.positions: del self.positions[clicked]
                    self._set_mode("select")
                    self.status.config(text=f"Estado {clicked} excluído.")
                    self.draw_all()
            return

        if clicked:
            self.selected_state = clicked
            self.dragging = (clicked, cx, cy)
            self.status.config(text=f"Selecionado {clicked}. Arraste para mover.")
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
        if edge:
            self._show_edge_context_menu(event, *edge)
            return
        state = self._find_state_at(cx, cy)
        if state:
            self._show_state_context_menu(event, state)

    def _show_state_context_menu(self, tk_event, state):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"Definir como inicial", command=lambda: self._set_start_from_menu(state))
        menu.add_command(label=f"Alternar final", command=lambda: self._toggle_final_from_menu(state))
        menu.add_separator()
        menu.add_command(label="Renomear", command=lambda: self._rename_state(state))
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
    
    def _rename_state(self, old_name):
        new_name = simpledialog.askstring("Renomear Estado", f"Novo nome para '{old_name}':", parent=self.root)
        if new_name and new_name not in self.automato.states:
            self._push_undo_snapshot()
            
            self.automato.states.remove(old_name)
            self.automato.states.add(new_name)

            if self.automato.start_state == old_name: self.automato.start_state = new_name
            if old_name in self.automato.final_states:
                self.automato.final_states.remove(old_name)
                self.automato.final_states.add(new_name)

            new_transitions = defaultdict(set)
            for (src, sym), dsts in self.automato.transitions.items():
                new_src = new_name if src == old_name else src
                new_dsts = {new_name if d == old_name else d for d in dsts}
                new_transitions[(new_src, sym)] = new_dsts
            self.automato.transitions = new_transitions

            if old_name in self.positions:
                self.positions[new_name] = self.positions.pop(old_name)
            
            self.draw_all()
        elif new_name:
            messagebox.showwarning("Renomear", f"O estado '{new_name}' já existe.")

    def _delete_state_from_menu(self, state):
        if messagebox.askyesno("Excluir", f"Tem certeza que deseja excluir o estado {state}?"):
            self._push_undo_snapshot()
            self.automato.remove_state(state)
            if state in self.positions: del self.positions[state]
            self.draw_all()

    def _edit_edge_label(self, src, dst):
        cur_label = self.edge_widgets.get((src, dst), {}).get("label", "")
        val = simpledialog.askstring("Editar Rótulo", "Símbolos (separados por vírgula):", initialvalue=cur_label, parent=self.root)
        if val is None: return
        self._push_undo_snapshot()
        
        symbols_to_remove = []
        for (s, sym), dsts in self.automato.transitions.items():
            if s == src and dst in dsts:
                symbols_to_remove.append(sym)
        for sym in symbols_to_remove:
            self.automato.remove_transition(src, sym, dst)

        for sym in (s.strip() or EPSILON for s in val.split(",")):
            if sym: self.automato.add_transition(src, sym, dst)
        self.draw_all()

    def _delete_edge(self, src, dst):
        if messagebox.askyesno("Excluir", f"Excluir todas as transições de {src} para {dst}?"):
            self._push_undo_snapshot()
            symbols_to_remove = []
            for (s, sym), dsts in self.automato.transitions.items():
                if s == src and dst in dsts:
                    symbols_to_remove.append(sym)
            
            for sym in symbols_to_remove:
                self.automato.remove_transition(src, sym, dst)
            
            self.draw_all()

    def _find_state_at(self, cx, cy):
        for sid, (sx, sy) in self.positions.items():
            if math.hypot(sx - cx, sy - cy) <= STATE_RADIUS: return sid
        return None

    def _find_edge_at(self, cx, cy):
        """Encontra a aresta (src, dst) mais próxima do ponto (cx, cy)."""
        click_radius = 20 / self.scale 
        for (src, dst), info in self.edge_widgets.items():
            tx, ty = info.get("text_pos", (None, None))
            if tx and math.hypot(tx-cx, ty-cy) <= click_radius:
                return src, dst
        return None

    def draw_all(self):
        self.canvas.delete("all")
        self.state_widgets.clear(); self.edge_widgets.clear()
        
        agg: DefaultDict[Tuple[str, str], Set[str]] = DefaultDict(set)
        for (src, sym), dsts in self.automato.transitions.items():
            for dst in dsts: agg[(src, dst)].add(sym)
        
        for (src, dst), syms in agg.items():
            if src not in self.positions or dst not in self.positions: continue
            x1, y1 = self._from_canvas(*self.positions[src])
            x2, y2 = self._from_canvas(*self.positions[dst])
            label = ",".join(sorted(list(syms)))

            # --- LÓGICA DE DESENHO DO LAÇO (src == dst) CORRIGIDA ---
            if src == dst:
                r = STATE_RADIUS * self.scale
                
                # Pontos para desenhar um laço suave com uma seta
                p1_x, p1_y = x1 - r * 0.7, y1 - r * 0.7  # Ponto de partida
                c1_x, c1_y = x1 - r * 1.5, y1 - r * 2.5  # Controle superior esquerdo
                c2_x, c2_y = x1 + r * 1.5, y1 - r * 2.5  # Controle superior direito
                p2_x, p2_y = x1 + r * 0.7, y1 - r * 0.7  # Ponto de chegada com a seta

                # Desenha a linha suave que forma o laço
                self.canvas.create_line(
                    p1_x, p1_y, c1_x, c1_y, c2_x, c2_y, p2_x, p2_y, 
                    smooth=True, arrow=tk.LAST, width=1.5
                )

                # Posição do texto no topo do laço
                tx, ty = x1, y1 - r * 2.2
                self.canvas.create_text(tx, ty, text=label, font=FONT)
                self.edge_widgets[(src, dst)] = {"label": label, "text_pos": self._to_canvas(tx, ty)}
            # --------------------------------------------------------
            else:
                dx, dy = x2 - x1, y2 - y1; dist = math.hypot(dx, dy) or 1
                ux, uy = dx/dist, dy/dist
                
                bend_amount = 0.25 if (dst,src) in agg else 0
                
                start_x, start_y = x1+ux*STATE_RADIUS*self.scale, y1+uy*STATE_RADIUS*self.scale
                end_x, end_y = x2-ux*STATE_RADIUS*self.scale, y2-uy*STATE_RADIUS*self.scale
                
                mid_x, mid_y = (start_x+end_x)/2, (start_y+end_y)/2
                ctrl_x, ctrl_y = mid_x - uy*dist*bend_amount, mid_y + ux*dist*bend_amount
                
                text_offset = 15 * self.scale
                txt_x = mid_x - uy*(dist*bend_amount + text_offset)
                txt_y = mid_y + ux*(dist*bend_amount + text_offset)

                self.canvas.create_line(start_x, start_y, ctrl_x, ctrl_y, end_x, end_y, smooth=True, width=1.5, arrow=tk.LAST)
                self.canvas.create_text(txt_x, txt_y, text=label, font=FONT)
                self.edge_widgets[(src, dst)] = {"label": label, "text_pos": self._to_canvas(txt_x, txt_y)}

        active_set = self.history[self.sim_step] if self.history else set()
        for sid in sorted(list(self.automato.states)):
            x_logic, y_logic = self.positions.get(sid, (100, 100))
            x, y = self._from_canvas(x_logic, y_logic)
            is_active = sid in active_set
            fill, outline, width = ("#e0f2fe", "#0284c7", 3) if is_active else ("white", "black", 2)
            self.canvas.create_oval(x-STATE_RADIUS*self.scale, y-STATE_RADIUS*self.scale, x+STATE_RADIUS*self.scale, y+STATE_RADIUS*self.scale, fill=fill, outline=outline, width=width)
            self.canvas.create_text(x, y, text=sid, font=FONT)
            if sid in self.automato.final_states:
                self.canvas.create_oval(x-(STATE_RADIUS-5)*self.scale, y-(STATE_RADIUS-5)*self.scale, x+(STATE_RADIUS-5)*self.scale, y+(STATE_RADIUS-5)*self.scale, outline="black", width=2)
        
        if self.automato.start_state and self.automato.start_state in self.positions:
            sx, sy = self._from_canvas(*self.positions[self.automato.start_state])
            self.canvas.create_line(sx-STATE_RADIUS*2*self.scale, sy, sx-STATE_RADIUS*self.scale, sy, arrow=tk.LAST, width=2)
        
        if self.result_indicator:
            color = "#16a34a" if self.result_indicator == "ACCEPT" else "#dc2626"
            self.canvas.create_text(self.canvas.winfo_width()-60, 30, text=self.result_indicator, font=("Helvetica", 16, "bold"), fill=color)

    def _reposition_states(self):
        self.positions = {}
        num_states = len(self.automato.states)
        if num_states == 0: return
        
        center_x, center_y = 400, 300
        radius = min(300, 60 * num_states / 3.14)
        
        sorted_states = sorted(list(self.automato.states))
        for i, s in enumerate(sorted_states):
            angle = 2 * math.pi * i / num_states
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            self.positions[s] = (x, y)

    def cmd_simulate(self):
        history, _ = self.automato.simulate_history(self.input_entry.get())
        if not history: messagebox.showwarning("Animar", "Autômato vazio ou sem estado inicial."); return
        self.history = [h for h, _ in history]
        self.sim_step, self.result_indicator, self.sim_playing = 0, None, False
        self.draw_all()

    def cmd_step(self):
        if not self.history or self.sim_step >= len(self.history) - 1:
            if self.history:
                accepted = bool(self.history[-1] & self.automato.final_states)
                self.result_indicator = "ACCEPT" if accepted else "REJECT"
                self.draw_all()
            else: messagebox.showwarning("Passo", "Nenhuma simulação em andamento.")
            return
        self.sim_step += 1
        self.draw_all()

    def cmd_play_pause(self):
        if not self.history: messagebox.showwarning("Play", "Nenhuma simulação em andamento."); return
        self.sim_playing = not self.sim_playing
        self.status.config(text="Reproduzindo..." if self.sim_playing else "Pausado")
        if self.sim_playing: self._playback_step()

    def _playback_step(self):
        if self.sim_playing and self.sim_step < len(self.history) - 1:
            self.cmd_step()
            self.root.after(ANIM_MS, self._playback_step)
        elif self.sim_playing:
            self.result_indicator = "ACCEPT" if bool(self.history[-1] & self.automato.final_states) else "REJECT"
            self.sim_playing = False
            self.draw_all()
    
    def cmd_reset_sim(self):
        self.history, self.sim_step, self.sim_playing, self.result_indicator = [], 0, False, None
        self.draw_all()
        self.status.config(text="Simulação reiniciada.")

    def cmd_batch_test(self):
        text = simpledialog.askstring("Testar Múltiplas Entradas", "Palavras separadas por vírgula (ε para vazio):", parent=self.root)
        if text is None: return
        items = [s.strip() for s in text.split(",")]
        results = [f"'{w}': {'ACEITO' if self.automato.simulate('' if w == 'ε' else w) else 'REJEITADO'}" for w in items]
        messagebox.showinfo("Resultados dos Testes", "\n".join(results))

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

# -------------------------
# BLOCO DE EXECUÇÃO
# -------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = EditorGUI(root)
    root.geometry("1200x800")
    root.mainloop()

