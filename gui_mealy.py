#!/usr/bin/env python3
"""
gui_mealy.py - Interface Tkinter para editar e simular Máquinas de Mealy.
"""
import json
import math
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
from typing import Dict, Tuple, Set, List, DefaultDict

from maquina_mealy import MaquinaMealy

STATE_RADIUS = 24
FONT = ("Helvetica", 11)
ACTIVE_MODE_COLOR = "#dbeafe"
DEFAULT_BTN_COLOR = "SystemButtonFace"
ANIM_MS = 400 # Milissegundos por passo na animação

class MealyGUI:
    def __init__(self, root: tk.Toplevel):
        self.root = root
        root.title("Editor de Máquinas de Mealy")
        root.geometry("1100x750")

        # Modelo de dados
        self.mealy_machine = MaquinaMealy()
        self.positions: Dict[str, Tuple[int, int]] = {}
        self.edge_widgets: Dict[Tuple[str, str], Dict] = {}
        self.mode = "select"
        self.transition_src = None
        self.dragging = None
        
        self.mode_buttons: Dict[str, tk.Button] = {}

        # Estado da simulação
        self.history: List[Tuple[str, str]] = []
        self.sim_step = 0
        self.sim_playing = False
        self.final_output_indicator = None

        # Construção da UI
        self._build_toolbar()
        self._build_canvas()
        self._build_simulation_bar()
        self._build_statusbar()
        self._bind_events()
        self.draw_all()
        self._update_mode_button_styles()

    def _build_toolbar(self):
        toolbar = tk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)

        self.mode_buttons["add_state"] = tk.Button(toolbar, text="Novo Estado", command=self.cmd_add_state)
        self.mode_buttons["add_state"].pack(side=tk.LEFT)
        
        self.mode_buttons["add_transition"] = tk.Button(toolbar, text="Nova Transição", command=self.cmd_add_transition)
        self.mode_buttons["add_transition"].pack(side=tk.LEFT)
        
        self.mode_buttons["set_start"] = tk.Button(toolbar, text="Definir Início", command=self.cmd_set_start)
        self.mode_buttons["set_start"].pack(side=tk.LEFT)

        tk.Label(toolbar, text="|").pack(side=tk.LEFT, padx=5)

        tk.Button(toolbar, text="Simulação Rápida", command=self.cmd_quick_simulate).pack(side=tk.LEFT)
        
        self.mode_label = tk.Label(toolbar, text="Modo: Selecionar")
        self.mode_label.pack(side=tk.RIGHT)

    def _build_canvas(self):
        self.canvas = tk.Canvas(self.root, width=1000, height=600, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def _build_simulation_bar(self):
        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=6)
        
        tk.Label(bottom, text="Entrada para Animação:").pack(side=tk.LEFT)
        self.input_entry = tk.Entry(bottom, width=30)
        self.input_entry.pack(side=tk.LEFT, padx=6)
        
        tk.Button(bottom, text="Animar", command=self.cmd_animate).pack(side=tk.LEFT)
        tk.Button(bottom, text="Passo", command=self.cmd_step).pack(side=tk.LEFT)
        tk.Button(bottom, text="Play/Pausar", command=self.cmd_play_pause).pack(side=tk.LEFT)
        tk.Button(bottom, text="Reiniciar", command=self.cmd_reset_sim).pack(side=tk.LEFT)
        
        tk.Label(bottom, text="|", padx=10).pack(side=tk.LEFT)
        
        tk.Label(bottom, text="Saída Gerada:").pack(side=tk.LEFT)
        self.output_label = tk.Label(bottom, text="", font=("Courier", 12), fg="#059669")
        self.output_label.pack(side=tk.LEFT)

    def _build_statusbar(self):
        self.status = tk.Label(self.root, text="Pronto", anchor="w", relief=tk.SUNKEN)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def _bind_events(self):
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_right_click)

    def _update_mode_button_styles(self):
        for mode_name, button in self.mode_buttons.items():
            current_base_mode = self.mode.replace("_src", "").replace("_dst", "")
            if mode_name == current_base_mode:
                button.config(background=ACTIVE_MODE_COLOR, relief=tk.SUNKEN)
            else:
                button.config(background=DEFAULT_BTN_COLOR, relief=tk.RAISED)

    def _set_mode(self, new_mode):
        self.mode = new_mode
        mode_text_map = {
            "select": "Modo: Selecionar",
            "add_state": "Modo: Adicionar Estado",
            "add_transition_src": "Modo: Adicionar Transição (Origem)",
            "add_transition_dst": "Modo: Adicionar Transição (Destino)",
            "set_start": "Modo: Definir Início",
        }
        self.mode_label.config(text=mode_text_map.get(new_mode, "Modo: Selecionar"))
        self.status.config(text=mode_text_map.get(new_mode, ""))
        self._update_mode_button_styles()

    def cmd_add_state(self): self._set_mode("add_state")
    def cmd_add_transition(self): self._set_mode("add_transition_src")
    def cmd_set_start(self): self._set_mode("set_start")

    def cmd_quick_simulate(self):
        input_str = simpledialog.askstring("Simulação Rápida", "Digite a cadeia de entrada:", parent=self.root)
        if input_str is None: return

        if not self.mealy_machine.start_state:
            messagebox.showwarning("Simulação", "Defina um estado inicial antes de simular.", parent=self.root)
            return
            
        output_str = self.mealy_machine.simulate(input_str)
        
        if output_str is not None:
            messagebox.showinfo("Resultado da Simulação", f"Entrada: '{input_str}'\nSaída:    '{output_str}'", parent=self.root)
        else:
            messagebox.showerror("Erro na Simulação", "A máquina travou. Verifique se todas as transições para a entrada fornecida estão definidas.", parent=self.root)

    def on_canvas_click(self, event):
        x, y = event.x, event.y
        if self.mode == "add_state":
            sid = f"q{len(self.mealy_machine.states)}"
            self.mealy_machine.add_state(sid)
            self.positions[sid] = (x, y)
            self._set_mode("select")
            self.draw_all()
            return

        clicked_state = self._find_state_at(x, y)

        if self.mode == "add_transition_src" and clicked_state:
            self.transition_src = clicked_state
            self._set_mode("add_transition_dst")
            self.status.config(text=f"Origem {clicked_state} selecionada. Clique no destino.")
            return
        
        if self.mode == "add_transition_dst" and clicked_state:
            src = self.transition_src
            dst = clicked_state
            label = simpledialog.askstring("Transição", "Digite a transição no formato 'entrada/saída':", parent=self.root)
            if label and '/' in label:
                inp, outp = label.split('/', 1)
                self.mealy_machine.add_transition(src, inp.strip(), dst, outp.strip())
                self.draw_all()
            self._set_mode("select")
            return

        if self.mode == "set_start" and clicked_state:
            self.mealy_machine.start_state = clicked_state
            self._set_mode("select")
            self.draw_all()
            return
            
        if clicked_state:
            self.dragging = (clicked_state, x, y)

    def on_canvas_drag(self, event):
        if self.dragging:
            sid, ox, oy = self.dragging
            dx, dy = event.x - ox, event.y - oy
            self.positions[sid] = (self.positions[sid][0] + dx, self.positions[sid][1] + dy)
            self.dragging = (sid, event.x, event.y)
            self.draw_all()
    
    def on_canvas_release(self, event):
        self.dragging = None
        
    def on_right_click(self, event):
        state = self._find_state_at(event.x, event.y)
        if state:
            self._show_state_context_menu(event, state)
            return
        edge = self._find_edge_at(event.x, event.y)
        if edge:
            self._show_edge_context_menu(event, edge[0], edge[1])

    def _show_state_context_menu(self, event, state):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"Definir '{state}' como inicial", command=lambda: self._set_start_state(state))
        menu.add_separator()
        menu.add_command(label=f"Excluir estado '{state}'", command=lambda: self._delete_state(state))
        menu.tk_popup(event.x_root, event.y_root)

    def _show_edge_context_menu(self, event, src, dst):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Editar transições...", command=lambda: self._edit_edge(src, dst))
        menu.add_separator()
        menu.add_command(label="Excluir todas as transições", command=lambda: self._delete_edge(src, dst))
        menu.tk_popup(event.x_root, event.y_root)
        
    def _set_start_state(self, state):
        self.mealy_machine.start_state = state
        self.draw_all()

    def _delete_state(self, state):
        if messagebox.askyesno("Excluir Estado", f"Tem certeza que deseja excluir o estado '{state}' e todas as suas transições?", parent=self.root):
            self.mealy_machine.remove_state(state)
            if state in self.positions:
                del self.positions[state]
            self.draw_all()

    def _delete_edge(self, src, dst):
        if messagebox.askyesno("Excluir Transições", f"Tem certeza que deseja excluir TODAS as transições de '{src}' para '{dst}'?", parent=self.root):
            transitions_to_remove = []
            for (s, inp), (d, outp) in self.mealy_machine.transitions.items():
                if s == src and d == dst:
                    transitions_to_remove.append(inp)
            for inp in transitions_to_remove:
                self.mealy_machine.remove_transition(src, inp)
            self.draw_all()

    def _edit_edge(self, src, dst):
        current_labels = []
        transitions_to_edit = []
        for (s, inp), (d, outp) in self.mealy_machine.transitions.items():
            if s == src and d == dst:
                current_labels.append(f"{inp}/{outp}")
                transitions_to_edit.append(inp)
        
        initial_value = ", ".join(current_labels)
        new_label_str = simpledialog.askstring("Editar Transições", 
            "Transições (formato 'in/out', separadas por vírgula):", 
            initialvalue=initial_value, parent=self.root)

        if new_label_str is not None:
            for inp in transitions_to_edit:
                self.mealy_machine.remove_transition(src, inp)
            new_labels = [label.strip() for label in new_label_str.split(',')]
            for label in new_labels:
                if '/' in label:
                    inp, outp = label.split('/', 1)
                    self.mealy_machine.add_transition(src, inp.strip(), dst, outp.strip())
            self.draw_all()

    def _find_state_at(self, x, y):
        for sid, (sx, sy) in self.positions.items():
            if math.hypot(sx - x, sy - y) <= STATE_RADIUS: return sid
        return None

    def _find_edge_at(self, x, y):
        for (src, dst), info in self.edge_widgets.items():
            tx, ty = info.get("text_pos", (None, None))
            if tx and math.hypot(tx - x, ty - y) <= 20: return src, dst
        return None

    def draw_all(self):
        self.canvas.delete("all")
        self.edge_widgets.clear()
        
        # Desenho das transições
        agg: DefaultDict[Tuple[str, str], List[str]] = DefaultDict(list)
        for (src, inp), (dst, outp) in self.mealy_machine.transitions.items():
            agg[(src, dst)].append(f"{inp}/{outp}")

        for (src, dst), labels in sorted(list(agg.items())):
            if src not in self.positions or dst not in self.positions: continue
            x1, y1 = self.positions[src]
            x2, y2 = self.positions[dst]
            label_text = ", ".join(sorted(labels))
            
            if src == dst:
                p1 = (x1 - STATE_RADIUS * 0.7, y1 - STATE_RADIUS * 0.7)
                c1 = (x1 - STATE_RADIUS * 1.5, y1 - STATE_RADIUS * 2.5)
                c2 = (x1 + STATE_RADIUS * 1.5, y1 - STATE_RADIUS * 2.5)
                p2 = (x1 + STATE_RADIUS * 0.7, y1 - STATE_RADIUS * 0.7)
                self.canvas.create_line(p1, c1, c2, p2, smooth=True, arrow=tk.LAST, width=1.5)
                tx, ty = x1, y1 - STATE_RADIUS * 2.2
                self.canvas.create_text(tx, ty, text=label_text, font=FONT)
                self.edge_widgets[(src, dst)] = {"text_pos": (tx, ty)}
            else:
                dx, dy = x2 - x1, y2 - y1; dist = math.hypot(dx, dy) or 1
                ux, uy = dx/dist, dy/dist
                bend = 0.25 if (dst, src) in agg else 0
                start_x, start_y = x1 + ux * STATE_RADIUS, y1 + uy * STATE_RADIUS
                end_x, end_y = x2 - ux * STATE_RADIUS, y2 - uy * STATE_RADIUS
                mid_x, mid_y = (start_x + end_x) / 2, (start_y + end_y) / 2
                ctrl_x, ctrl_y = mid_x - uy*dist*bend, mid_y + ux*dist*bend
                text_offset = 15
                txt_x = mid_x - uy*(dist*bend + text_offset)
                txt_y = mid_y + ux*(dist*bend + text_offset)
                self.canvas.create_line(start_x, start_y, ctrl_x, ctrl_y, end_x, end_y, smooth=True, width=1.5, arrow=tk.LAST)
                self.canvas.create_text(txt_x, txt_y, text=label_text, font=FONT)
                self.edge_widgets[(src, dst)] = {"text_pos": (txt_x, txt_y)}
        
        # Desenho dos estados
        active_state = self.history[self.sim_step][0] if self.history else None
        for sid in sorted(list(self.mealy_machine.states)):
            x, y = self.positions.get(sid, (100, 100))
            is_active = (sid == active_state)
            fill, outline, width = ("#e0f2fe", "#0284c7", 3) if is_active else ("white", "black", 2)
            self.canvas.create_oval(x-STATE_RADIUS, y-STATE_RADIUS, x+STATE_RADIUS, y+STATE_RADIUS, fill=fill, outline=outline, width=width)
            self.canvas.create_text(x, y, text=sid, font=FONT)
        
        # Seta inicial
        if self.mealy_machine.start_state and self.mealy_machine.start_state in self.positions:
            sx, sy = self.positions[self.mealy_machine.start_state]
            self.canvas.create_line(sx-STATE_RADIUS*2, sy, sx-STATE_RADIUS, sy, arrow=tk.LAST, width=2)

        # Indicador de saída final
        if self.final_output_indicator is not None:
            color = "#059669" if self.final_output_indicator != "TRAVOU" else "#dc2626"
            text = f"Saída Final: {self.final_output_indicator}"
            self.canvas.create_text(self.canvas.winfo_width()-10, 20, text=text, font=("Helvetica", 14, "bold"), fill=color, anchor="e")

    # --- Métodos de Simulação ---

    def cmd_animate(self):
        if not self.mealy_machine.start_state:
            messagebox.showwarning("Animar", "Máquina não possui estado inicial.", parent=self.root)
            return
        
        input_str = self.input_entry.get()
        self.history, final_output = self.mealy_machine.simulate_history(input_str)
        
        self.sim_step = 0
        self.sim_playing = False
        self.final_output_indicator = None # Limpa o indicador do canvas
        self.status.config(text=f"Iniciando animação para a entrada '{input_str}'.")
        self.draw_all()
        self.output_label.config(text="") # Limpa o label da saída

    def cmd_step(self):
        if not self.history:
            self.status.config(text="Nenhuma simulação em andamento. Clique em 'Animar' primeiro.")
            return

        # Verifica se está no último passo
        if self.sim_step >= len(self.history) - 1:
            _, final_output = self.mealy_machine.simulate_history(self.input_entry.get())
            self.final_output_indicator = final_output if final_output is not None else "TRAVOU"
            self.status.config(text="Fim da simulação.")
            self.draw_all()
            return
        
        self.sim_step += 1
        current_output = self.history[self.sim_step][1]
        self.output_label.config(text=current_output)
        self.status.config(text=f"Processando passo {self.sim_step}...")
        self.draw_all()

    def cmd_play_pause(self):
        if not self.history:
            self.status.config(text="Nenhuma simulação em andamento. Clique em 'Animar' primeiro.")
            return
            
        self.sim_playing = not self.sim_playing
        self.status.config(text="Reproduzindo..." if self.sim_playing else "Pausado.")
        if self.sim_playing:
            self._playback_step()

    def _playback_step(self):
        if self.sim_playing and self.sim_step < len(self.history) - 1:
            self.cmd_step()
            self.root.after(ANIM_MS, self._playback_step)
        elif self.sim_playing: # Chegou ao fim durante o play
            self.sim_playing = False
            self.cmd_step() # Executa o último passo para mostrar o resultado final
            self.status.config(text="Reprodução finalizada.")
    
    def cmd_reset_sim(self):
        self.history = []
        self.sim_step = 0
        self.sim_playing = False
        self.final_output_indicator = None
        self.output_label.config(text="")
        self.status.config(text="Simulação reiniciada.")
        self.draw_all()

