#!/usr/bin/env python3
"""
gui_moore.py - Interface Tkinter para editar e simular Máquinas de Moore.
"""
import json
import math
import tkinter as tk, tkinter.ttk as ttk
from tkinter import simpledialog, filedialog, messagebox
from typing import Dict, Tuple, List, DefaultDict

from maquina_moore import MaquinaMoore

STATE_RADIUS = 28 # Um pouco maior para caber a saída
FONT = ("Helvetica", 11)
ANIM_MS = 400

class MooreGUI:
    def __init__(self, root: tk.Toplevel):
        self.root = root
        root.title("Editor de Máquinas de Moore")
        root.state('zoomed')
        
        style = ttk.Style()
        style.configure("TButton", padding=(10, 5))
        style.configure("Accent.TButton", padding=(10, 5))
        
        self.moore_machine = MaquinaMoore()
        self.positions: Dict[str, Tuple[int, int]] = {}
        self.edge_widgets: Dict[Tuple[str, str], Dict] = {}
        self.mode = "select"
        self.transition_src = None
        self.dragging = None
        self.mode_buttons: Dict[str, tk.Button] = {}
        self.history: List[Tuple[str, str]] = []
        self.sim_step = 0
        self.sim_playing = False

        # Transform (zoom/pan)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_last = None
        self.final_output_indicator = None

        self._build_toolbar()
        self._build_canvas()
        self._build_simulation_bar()
        self._build_statusbar()
        self._bind_events()
        self.draw_all()

    def _build_toolbar(self):
        toolbar = tk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5, 10))

        self.mode_buttons["add_state"] = ttk.Button(toolbar, text="Novo Estado", command=self.cmd_add_state)
        self.mode_buttons["add_state"].pack(side=tk.LEFT, padx=2)
        self.mode_buttons["add_transition"] = ttk.Button(toolbar, text="Nova Transição", command=self.cmd_add_transition)
        self.mode_buttons["add_transition"].pack(side=tk.LEFT, padx=2)
        self.mode_buttons["set_start"] = ttk.Button(toolbar, text="Definir Início", command=self.cmd_set_start)
        self.mode_buttons["set_start"].pack(side=tk.LEFT, padx=2)

        self.mode_label = ttk.Label(toolbar, text="Modo: Selecionar")
        self.mode_label.pack(side=tk.RIGHT)

    def _build_canvas(self):
        self.canvas = tk.Canvas(self.root, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=0)

    def _build_simulation_bar(self):
        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Label(bottom, text="Entrada para Simulação:").pack(side=tk.LEFT)
        self.input_entry = ttk.Entry(bottom, width=30)
        self.input_entry.pack(side=tk.LEFT, padx=6)
        ttk.Button(bottom, text="Simular", command=self.cmd_animate, style="Accent.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Passo", command=self.cmd_step).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Play/Pausar", command=self.cmd_play_pause).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Reiniciar", command=self.cmd_reset_sim).pack(side=tk.LEFT, padx=2)
        ttk.Separator(bottom, orient='vertical').pack(side=tk.LEFT, padx=8, fill='y')
        ttk.Label(bottom, text="Saída Gerada:").pack(side=tk.LEFT)
        self.output_canvas = tk.Canvas(bottom, height=40, bg="white", highlightthickness=0)
        self.output_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    def _build_statusbar(self):
        self.status = tk.Label(self.root, text="Pronto", anchor="w", relief=tk.SUNKEN)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def _bind_events(self):
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


    def _update_mode_button_styles(self):
        for name, btn in self.mode_buttons.items():
            base_mode = self.mode.replace("_src", "").replace("_dst", "")
            btn.config(style="Accent.TButton" if name == base_mode else "TButton")

    def _set_mode(self, new_mode):
        self.mode = new_mode
        mode_map = {
            "select": "Modo: Selecionar", "add_state": "Modo: Adicionar Estado",
            "add_transition_src": "Modo: Adicionar Transição (Origem)",
            "add_transition_dst": "Modo: Adicionar Transição (Destino)",
            "set_start": "Modo: Definir Início"
        }
        cursor_map = {
            "add_state": "crosshair", "add_transition_src": "hand2",
            "add_transition_dst": "hand2", "set_start": "hand2"
        }
        self.canvas.config(cursor=cursor_map.get(new_mode, "arrow"))
        self.mode_label.config(text=mode_map.get(new_mode, "Modo: Selecionar"))
        self._update_mode_button_styles()

    def cmd_add_state(self): self._set_mode("add_state")
    def cmd_add_transition(self): self._set_mode("add_transition_src")
    def cmd_set_start(self): self._set_mode("set_start")

    def cmd_animate(self):
        input_str = self.input_entry.get()
        if not self.moore_machine.start_state:
            messagebox.showwarning("Simular", "Defina um estado inicial.", parent=self.root)
            return
        
        self.history, _ = self.moore_machine.simulate_history(input_str)
        self.sim_step = 0
        self.sim_playing = False
        self.final_output_indicator = None
        self.status.config(text=f"Iniciando simulação para a entrada '{input_str}'.")
        self.draw_all()

    def cmd_step(self):
        if not self.history:
            self.status.config(text="Nenhuma simulação em andamento. Clique em 'Simular'.")
            return

        if self.sim_step >= len(self.history) - 1:
            _, final_output = self.moore_machine.simulate_history(self.input_entry.get())
            self.final_output_indicator = final_output if final_output is not None else "TRAVOU"
            self.status.config(text="Fim da simulação.")
            self.draw_all()
            return
        
        self.sim_step += 1
        self.status.config(text=f"Processando passo {self.sim_step}...")
        self.draw_all()

    def cmd_play_pause(self):
        if not self.history: return
        self.sim_playing = not self.sim_playing
        self.status.config(text="Reproduzindo..." if self.sim_playing else "Pausado.")
        if self.sim_playing: self._playback_step()

    def _playback_step(self):
        if self.sim_playing and self.sim_step < len(self.history) - 1:
            self.cmd_step()
            self.root.after(ANIM_MS, self._playback_step)
        elif self.sim_playing:
            self.sim_playing = False
            self.cmd_step()

    def on_canvas_click(self, event):
        x, y = event.x, event.y
        clicked_state = self._find_state_at(x, y)

        if self.mode == "add_state":
            state_name = f"q{len(self.moore_machine.states)}"
            output_sym = simpledialog.askstring("Saída do Estado", "Símbolo de saída para o estado:", parent=self.root)
            if output_sym is not None:
                self.moore_machine.add_state(state_name, output_sym)
                self.positions[state_name] = (x, y)
                self._set_mode("select")
                self.draw_all()
            return

        if self.mode == "add_transition_src" and clicked_state:
            self.transition_src = clicked_state
            self._set_mode("add_transition_dst")
            self.status.config(text=f"Origem {clicked_state} selecionada. Clique no destino.")
            return
        
        if self.mode == "add_transition_dst" and clicked_state:
            src, dst = self.transition_src, clicked_state
            inp = simpledialog.askstring("Transição", "Símbolo de entrada:", parent=self.root)
            if inp:
                self.moore_machine.add_transition(src, inp.strip(), dst)
                self.draw_all()
            self._set_mode("select")
            return

        if self.mode == "set_start" and clicked_state:
            self.moore_machine.start_state = clicked_state
            self._set_mode("select")
            self.draw_all()
            return
            
        if clicked_state:
            self.dragging = (clicked_state, cx, cy)

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
        self.dragging = None
        
    def on_right_click(self, event):
        state = self._find_state_at(*self._to_canvas(event.x, event.y))
        if state:
            self._show_state_context_menu(event, state)

    def on_canvas_double_click(self, event):
        """Handles double-clicks on the canvas to edit transitions."""
        cx, cy = self._to_canvas(event.x, event.y)
        edge = self._find_edge_at(cx, cy)
        if edge:
            self._edit_edge(edge[0], edge[1])

    def _show_state_context_menu(self, event, state):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"Definir como inicial", command=lambda: self._set_start_state(state))
        menu.add_command(label=f"Renomear", command=lambda: self._rename_state(state))
        menu.add_command(label=f"Editar Saída", command=lambda: self._edit_state_output(state))
        menu.add_separator()
        menu.add_command(label=f"Excluir", command=lambda: self._delete_state(state))
        menu.tk_popup(event.x_root, event.y_root)
        
    def _set_start_state(self, state):
        self.moore_machine.start_state = state
        self.draw_all()

    def _delete_state(self, state):
        if messagebox.askyesno("Excluir", f"Excluir o estado '{state}'?", parent=self.root):
            self.moore_machine.remove_state(state)
            if state in self.positions: del self.positions[state]
            self.draw_all()

    def _rename_state(self, old_name: str):
        new_name = simpledialog.askstring("Renomear", f"Novo nome para '{old_name}':", initialvalue=old_name, parent=self.root)
        if new_name and new_name != old_name:
            try:
                self.moore_machine.rename_state(old_name, new_name)
                self.positions[new_name] = self.positions.pop(old_name)
                self.draw_all()
            except ValueError as e:
                messagebox.showerror("Erro", str(e), parent=self.root)

    def _edit_state_output(self, state: str):
        current_output = self.moore_machine.output_function.get(state, "")
        new_output = simpledialog.askstring("Editar Saída", f"Símbolo de saída para '{state}':", initialvalue=current_output, parent=self.root)
        if new_output is not None:
            self.moore_machine.output_function[state] = new_output
            self.draw_all()

    def _edit_edge(self, src: str, dst: str):
        """Abre um diálogo para editar os símbolos de entrada de uma transição."""
        transitions_to_edit = []
        for (s, inp), d in self.moore_machine.transitions.items():
            if s == src and d == dst:
                transitions_to_edit.append(inp)
        
        initial_value = ", ".join(sorted(transitions_to_edit))
        new_label_str = simpledialog.askstring("Editar Transições", 
            "Símbolos de entrada (separados por vírgula):", 
            initialvalue=initial_value, parent=self.root)

        if new_label_str is not None:
            # Remove as transições antigas
            for inp in transitions_to_edit:
                del self.moore_machine.transitions[(src, inp)]
            # Adiciona as novas
            for inp in [s.strip() for s in new_label_str.split(',') if s.strip()]:
                self.moore_machine.add_transition(src, inp, dst)
            self.draw_all()

    def _to_canvas(self, x, y):
        return (x - self.offset_x) / self.scale, (y - self.offset_y) / self.scale

    def _from_canvas(self, x, y):
        return x * self.scale + self.offset_x, y * self.scale + self.offset_y

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

    def _find_state_at(self, cx, cy):
        for sid, (sx, sy) in self.positions.items():
            if math.hypot(sx - cx, sy - cy) <= STATE_RADIUS: return sid
        return None
    
    def _find_edge_at(self, cx, cy):
        """Encontra uma aresta (transição) nas coordenadas do canvas."""
        for (src, dst), info in self.edge_widgets.items():
            tx, ty = info.get("text_pos", (0,0))
            if tx and math.hypot(tx - cx, ty - cy) <= 20: return src, dst
        return None

    def _draw_output_tape(self):
        """Desenha a fita de saída gerada no canvas."""
        self.output_canvas.delete("all")
        
        output_str = self.history[self.sim_step][1] if self.history else ""
        
        cell_width = 35
        cell_height = 35
        y_pos = (self.output_canvas.winfo_height() / 2) - (cell_height / 2)
        x_pos = 10

        for char in output_str:
            self.output_canvas.create_rectangle(x_pos, y_pos, x_pos + cell_width, y_pos + cell_height,
                                                fill="#f0fdf4", outline="#86efac", width=1.5)
            self.output_canvas.create_text(x_pos + cell_width / 2, y_pos + cell_height / 2,
                                           text=char, font=("Courier", 16, "bold"), fill="#15803d")
            x_pos += cell_width + 5

    def draw_all(self):
        self.canvas.delete("all")
        self.edge_widgets.clear()
        
        # Lógica para destacar transição ativa
        active_state = self.history[self.sim_step][0] if self.history else None
        prev_state = self.history[self.sim_step - 1][0] if self.history and self.sim_step > 0 else None
        input_char = self.input_entry.get()[self.sim_step - 1] if self.history and self.sim_step > 0 else None

        # Agrega transições
        agg: DefaultDict[Tuple[str, str], List[str]] = DefaultDict(list)
        for (src, inp), dst in self.moore_machine.transitions.items():
            agg[(src, dst)].append(inp)

        for (src, dst), labels in sorted(list(agg.items())):
            if src not in self.positions or dst not in self.positions: continue
            x1, y1 = self._from_canvas(*self.positions[src])
            x2, y2 = self._from_canvas(*self.positions[dst])
            label_text = ", ".join(sorted(labels)).replace(EPSILON, "ε")

            is_active_transition = (src == prev_state and dst == active_state and input_char in labels)
            color = "#16a34a" if is_active_transition else "black"
            width = 3 if is_active_transition else 1.5
            
            if src == dst:
                r = STATE_RADIUS * self.scale
                p1 = (x1 - r * 0.7, y1 - r * 0.7)
                c1 = (x1 - r * 1.5, y1 - r * 2.5)
                c2 = (x1 + r * 1.5, y1 - r * 2.5)
                p2 = (x1 + r * 0.7, y1 - r * 0.7)
                self.canvas.create_line(p1, c1, c2, p2, smooth=True, arrow=tk.LAST, width=width, fill=color)
                tx, ty = x1, y1 - r * 2.3
                text_id = self.canvas.create_text(tx, ty, text=label_text, font=FONT, fill=color)
                self.canvas.tag_bind(text_id, "<Double-Button-1>", lambda e, s=src, d=dst: self._edit_edge(s, d))
                self.edge_widgets[(src, dst)] = {"text_pos": self._to_canvas(tx, ty)}
            else:
                dx, dy = x2 - x1, y2 - y1; dist = math.hypot(dx, dy) or 1
                ux, uy = dx/dist, dy/dist
                bend = 0.25 if (dst, src) in agg else 0
                offset = 15*self.scale if (dst,src) in agg else 0
                start_x, start_y = x1+ux*STATE_RADIUS*self.scale, y1+uy*STATE_RADIUS*self.scale
                end_x, end_y = x2-ux*STATE_RADIUS*self.scale, y2-uy*STATE_RADIUS*self.scale
                mid_x, mid_y = (start_x + end_x) / 2, (start_y + end_y) / 2
                ctrl_x, ctrl_y = mid_x - uy*offset, mid_y + ux*offset
                self.canvas.create_line(start_x, start_y, ctrl_x, ctrl_y, end_x, end_y, smooth=True, width=width, arrow=tk.LAST, fill=color)
                txt_x, txt_y = mid_x-uy*(offset+15), mid_y+ux*(offset+15)
                text_id = self.canvas.create_text(txt_x, txt_y, text=label_text, font=FONT, fill=color)
                self.canvas.tag_bind(text_id, "<Double-Button-1>", lambda e, s=src, d=dst: self._edit_edge(s, d))
                self.edge_widgets[(src, dst)] = {"text_pos": self._to_canvas(txt_x, txt_y)}
        
        # Desenha estados
        for sid in sorted(list(self.moore_machine.states)):
            x_logic, y_logic = self.positions.get(sid, (100, 100))
            x, y = self._from_canvas(x_logic, y_logic)
            output_sym = self.moore_machine.output_function.get(sid, '?')
            state_label = f"{sid}\n—\n{output_sym}"
            
            is_active = (sid == active_state)
            fill, outline, width = ("#e0f2fe", "#0284c7", 3) if is_active else ("white", "black", 2)
            
            self.canvas.create_oval(x-STATE_RADIUS*self.scale, y-STATE_RADIUS*self.scale, x+STATE_RADIUS*self.scale, y+STATE_RADIUS*self.scale, fill=fill, outline=outline, width=width)
            self.canvas.create_text(x, y, text=state_label, font=FONT, justify=tk.CENTER)
        
        # Seta inicial
        if self.moore_machine.start_state and self.moore_machine.start_state in self.positions:
            sx, sy = self._from_canvas(*self.positions[self.moore_machine.start_state])
            self.canvas.create_line(sx-STATE_RADIUS*2*self.scale, sy, sx-STATE_RADIUS*self.scale, sy, arrow=tk.LAST, width=2)

        # Indicador de saída final
        if self.final_output_indicator is not None:
            color = "#059669" if self.final_output_indicator != "TRAVOU" else "#dc2626"
            text = f"Saída Final: {self.final_output_indicator}"
            self.canvas.create_text(self.canvas.winfo_width()-10, 20, text=text, font=("Helvetica", 14, "bold"), fill=color, anchor="e")

        self._draw_output_tape()

    def cmd_reset_sim(self):
        self.history, self.sim_step, self.sim_playing, self.final_output_indicator = [], 0, False, None
        self.status.config(text="Simulação reiniciada.")
        self.draw_all()