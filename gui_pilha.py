#!/usr/bin/env python3
"""
gui_pilha.py - Interface para Autômatos de Pilha (PDA).
"""
import os
import math
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox, ttk
from collections import defaultdict

from PIL import Image, ImageTk, ImageEnhance
from pilha import AutomatoPilha, EPSILON, snapshot_of_pda, restore_from_pda_snapshot

ANIM_MS = 500

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        x = self.widget.winfo_pointerx() + 15
        y = self.widget.winfo_pointery() + 10

        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(tw, text=self.text, justify='left',
                       background="#ffffe0", relief='solid', borderwidth=1,
                       font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tooltip(self, event):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None

class PilhaGUI:
    def __init__(self, root: tk.Toplevel):
        self.root = root
        root.title("Editor de Autômatos de Pilha")
        root.state('zoomed')

        # Estilo para aumentar o tamanho dos botões
        style = ttk.Style()
        style.configure("TButton", padding=(8, 6))
        style.configure("Accent.TButton", padding=(8, 6))
        style.configure("TMenubutton", padding=(8, 6))

        self.automato = AutomatoPilha()
        self.positions = {}
        self.mode = "select"
        self.dragging = None
        self.mode_buttons = {}
        self.transition_src = None
        self.pinned_mode = "select"
        self.icons = {}

        # Undo/Redo
        self.undo_stack: List[str] = []
        self.redo_stack: List[str] = []

        # Simulação
        self.history = []
        self.sim_step = 0
        self.sim_playing = False
        self.result_indicator = None

        # Transform (zoom/pan)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_last = None
        self.current_filepath = None

        self._build_toolbar()
        self._build_canvas()
        self._build_bottom_bar()
        self._build_statusbar()
        self._bind_events()
        self._push_undo_snapshot()
        self.draw_all()

    def _build_toolbar(self):
        toolbar = tk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5, 10))
        
        # --- Menu Arquivo ---
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

        # --- Menu Exportar ---
        export_menu = tk.Menu(toolbar, tearoff=0)
        export_menu.add_command(label="Exportar para TikZ (.tex)", command=self.cmd_export_tikz)
        export_menu.add_command(label="Exportar para SVG (.svg)", command=self.cmd_export_svg)
        export_menu.add_command(label="Exportar para PNG (.png)", command=self.cmd_export_png)
        self._create_toolbar_menubutton(toolbar, "exportar", "Exportar", export_menu)

        self.mode_label = ttk.Label(toolbar, text="Modo: Selecionar", font=("Helvetica", 11, "bold"))
        self.mode_label.pack(side=tk.RIGHT, padx=10)

    def _create_toolbar_menubutton(self, parent, icon_name, tooltip_text, menu):
        icon_path = os.path.join("icons", f"{icon_name}.png")
        try:
            img = Image.open(icon_path)
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(1.5)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.1)
            img = img.resize((32, 32), Image.Resampling.LANCZOS)
            self.icons[icon_name] = ImageTk.PhotoImage(img)
            button = ttk.Menubutton(parent, image=self.icons[icon_name])
        except FileNotFoundError:
            button = ttk.Menubutton(parent, text=tooltip_text)
            print(f"Aviso: Ícone não encontrado em '{icon_path}'. Usando texto.")
        
        button["menu"] = menu
        button.pack(side=tk.LEFT, padx=2)
        Tooltip(button, tooltip_text)

    def _create_toolbar_button(self, parent, icon_name, tooltip_text, command):
        icon_path = os.path.join("icons", f"{icon_name}.png")
        try:
            img = Image.open(icon_path)
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(1.5)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.1)
            img = img.resize((32, 32), Image.Resampling.LANCZOS)
            self.icons[icon_name] = ImageTk.PhotoImage(img)
            button = ttk.Button(parent, image=self.icons[icon_name], command=command)
        except FileNotFoundError:
            button = ttk.Button(parent, text=tooltip_text, command=command)
            print(f"Aviso: Ícone não encontrado em '{icon_path}'. Usando texto.")
        
        button.pack(side=tk.LEFT, padx=2)
        self.mode_buttons[icon_name] = button
        Tooltip(button, tooltip_text)

        button.bind("<Enter>", lambda e, m=icon_name: self._set_mode(m))
        button.bind("<Leave>", lambda e: self._set_mode(self.pinned_mode))

    def _build_canvas(self):
        self.canvas = tk.Canvas(self.root, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=0)

    def _build_bottom_bar(self):
        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Label(bottom, text="Entrada:", font=("Helvetica", 10)).pack(side=tk.LEFT)
        self.input_entry = ttk.Entry(bottom, width=40)
        self.input_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom, text="Simular", command=self.cmd_start_simulation, style="Accent.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Passo", command=self.cmd_step).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Play/Pausar", command=self.cmd_play_pause).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Reiniciar", command=self.cmd_reset_sim).pack(side=tk.LEFT, padx=2)

        # Canvas para desenhar a pilha e a fita de entrada
        self.sim_display_canvas = tk.Canvas(bottom, height=60, bg="white", highlightthickness=0)
        self.sim_display_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

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
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())


    def _update_mode_button_styles(self):
        # O estilo de destaque reflete o modo PINADO (fixo)
        for name, btn in self.mode_buttons.items():
            is_pinned = (name == self.pinned_mode.replace("_src", "").replace("_dst", ""))
            btn.config(style="Accent.TButton" if is_pinned else "TButton")

    def _set_mode(self, new_mode, pinned=False):
        if pinned:
            self.pinned_mode = new_mode

        self.mode = new_mode
        cursor_map = {
            "add_state": "crosshair",
            "add_transition_src": "hand2",
            "add_transition_dst": "hand2",
            "set_start": "hand2",
            "toggle_final": "hand2",
            "delete_state": "X_cursor",
        }
        self.canvas.config(cursor=cursor_map.get(new_mode, "arrow"))
        mode_text_map = {
            "select": "Modo: Selecionar",
            "add_state": "Modo: Adicionar Estado",
            "add_transition_src": "Modo: Adicionar Transição (Origem)",
            "add_transition_dst": "Modo: Adicionar Transição (Destino)",
            "set_start": "Modo: Definir Início",
            "toggle_final": "Modo: Alternar Final",
            "delete_state": "Modo: Excluir Estado",
        }
        self.mode_label.config(text=mode_text_map.get(new_mode, "Modo: Selecionar"))
        self._update_mode_button_styles()

    def cmd_add_state(self):
        self._set_mode("add_state", pinned=True)
        self.status.config(text="Clique no canvas para adicionar um estado.")

    def cmd_add_transition(self):
        self._set_mode("add_transition_src", pinned=True)
        self.status.config(text="Clique no estado de origem.")

    def cmd_set_start(self):
        self._set_mode("set_start", pinned=True)
        self.status.config(text="Clique em um estado para torná-lo inicial.")

    def cmd_toggle_final(self):
        self._set_mode("toggle_final", pinned=True)
        self.status.config(text="Clique em um estado para alternar seu status de final.")

    def cmd_delete_state_mode(self):
        self._set_mode("delete_state", pinned=True)
        self.status.config(text="Clique em um estado para excluí-lo.")

    def cmd_open(self):
        """Abre um arquivo de Autômato de Pilha (.json)."""
        path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("PDA Files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                snapshot = f.read()
            self.automato, self.positions = restore_from_pda_snapshot(snapshot)
            self.current_filepath = path
            self.undo_stack = [snapshot]
            self.redo_stack.clear()
            self.root.title(f"Editor de Autômatos de Pilha — {self.current_filepath}")
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
                    f.write(snapshot_of_pda(self.automato, self.positions))
                self.status.config(text=f"Arquivo salvo em '{self.current_filepath}'.")
            except Exception as e:
                messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo:\n{e}", parent=self.root)

    def cmd_save_as(self):
        """Abre um diálogo para salvar o autômato em um novo arquivo."""
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("PDA Files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        self.current_filepath = path
        self.root.title(f"Editor de Autômatos de Pilha — {self.current_filepath}")
        self.cmd_save()

    def cmd_export_tikz(self):
        messagebox.showinfo("Exportar", "A exportação para TikZ ainda não foi implementada para Autômatos de Pilha.", parent=self.root)

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

    def cmd_start_simulation(self):
        input_str = self.input_entry.get()
        if not self.automato.start_state:
            messagebox.showwarning("Simulação", "Defina um estado inicial.", parent=self.root)
            return
        
        self.history, _ = self.automato.simulate_history(input_str)
        self.sim_step = 0
        self.sim_playing = False
        self.result_indicator = None
        self.draw_all()
        self.status.config(text=f"Simulação iniciada para '{input_str}'.")

    def cmd_step(self):
        if not self.history:
            self.status.config(text="Nenhuma simulação em andamento.")
            return
        
        if self.sim_step < len(self.history) - 1:
            self.sim_step += 1
            self.draw_all()
        else:
            self.status.config(text="Fim da simulação.")
            # Mostra o resultado final
            _, accepted = self.automato.simulate_history(self.input_entry.get())
            self.result_indicator = "ACEITA" if accepted else "REJEITADA"
            self.draw_all()

    def cmd_play_pause(self):
        if not self.history: return
        self.sim_playing = not self.sim_playing
        if self.sim_playing:
            self.status.config(text="Reproduzindo...")
            self._playback_step()
        else:
            self.status.config(text="Pausado.")

    def _playback_step(self):
        if self.sim_playing and self.sim_step < len(self.history) - 1:
            self.cmd_step()
            self.root.after(ANIM_MS, self._playback_step)
        else:
            # Se a reprodução terminou, executa o último passo para mostrar o resultado
            self.sim_playing = False
            if self.sim_step >= len(self.history) -1:
                self.cmd_step() # Executa o último passo para mostrar o resultado

    def on_canvas_click(self, event):
        cx, cy = self._to_canvas(event.x, event.y)
        clicked_state = self._find_state_at(cx, cy)

        if self.mode == "delete_state":
            if clicked_state:
                if messagebox.askyesno("Excluir", f"Excluir estado {clicked_state}?", parent=self.root):
                    self._push_undo_snapshot()
                    self.automato.remove_state(clicked_state)
                    if clicked_state in self.positions: del self.positions[clicked_state]
                    self._set_mode("select", pinned=True)
                    self.draw_all()
            return

        if self.mode == "add_state":
            state_name = f"q{len(self.automato.states)}"
            self._push_undo_snapshot()
            self.automato.add_state(state_name)
            self.positions[state_name] = (cx, cy)
            self.draw_all()
        elif self.mode == "set_start" and clicked_state:
            self._push_undo_snapshot()
            self.automato.start_state = clicked_state
            self._set_mode("select", pinned=True)
            self.draw_all()
        elif self.mode == "toggle_final" and clicked_state:
            self._push_undo_snapshot()
            if clicked_state in self.automato.final_states:
                self.automato.final_states.remove(clicked_state)
            else:
                self.automato.final_states.add(clicked_state)
            self._set_mode("select", pinned=True)
            self.draw_all()
        elif self.mode == "add_transition_src" and clicked_state:
            self.transition_src = clicked_state
            self._set_mode("add_transition_dst", pinned=True)
            self.status.config(text=f"Origem {clicked_state}. Clique no destino.")
        elif self.mode == "add_transition_dst" and clicked_state:
            src, dst = self.transition_src, clicked_state
            label = simpledialog.askstring("Transição de Pilha", 
                "Formato: 'entrada, desempilha / empilha'\n(Use & para vazio)",
                parent=self.root)
            if label and '/' in label:
                try:
                    read_part, push_part = label.split('/', 1)
                    input_sym, pop_sym = (read_part.split(',') + [EPSILON])[:2]
                    push_syms = push_part.strip()
                    
                    self._push_undo_snapshot()
                    self.automato.add_transition(src, input_sym.strip(), pop_sym.strip(), dst, push_syms)
                    self.draw_all()
                except (ValueError, IndexError) as e:
                    messagebox.showerror("Erro de Formato", f"Formato de transição inválido. Use 'entrada, desempilha / empilha'.\n\nDetalhe: {e}", parent=self.root)
            
            self._set_mode("select", pinned=True) # Garante que o modo volte ao normal mesmo se o usuário cancelar ou errar
        
        elif clicked_state:
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
        if self.dragging: self._push_undo_snapshot()
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
        menu.add_command(label="Definir como inicial", command=lambda: self._set_start_from_menu(state))
        menu.add_command(label="Alternar final", command=lambda: self._toggle_final_from_menu(state))
        menu.add_command(label="Renomear", command=lambda: self._rename_state_from_menu(state))
        menu.add_separator()
        menu.add_command(label="Excluir", command=lambda: self._delete_state_from_menu(state))
        menu.tk_popup(event.x_root, event.y_root)

    def _set_start_from_menu(self, state):
        self._push_undo_snapshot()
        self.automato.start_state = state
        self.draw_all()

    def _rename_state_from_menu(self, old_name: str):
        """Abre um diálogo para renomear um estado."""
        new_name = simpledialog.askstring("Renomear Estado", f"Digite o novo nome para '{old_name}':",
                                          initialvalue=old_name, parent=self.root)
        
        if new_name and new_name != old_name:
            try:
                self._push_undo_snapshot()
                self.automato.rename_state(old_name, new_name)
                self.positions[new_name] = self.positions.pop(old_name)
                self.draw_all()
                self.status.config(text=f"Estado '{old_name}' renomeado para '{new_name}'.")
            except ValueError as e:
                messagebox.showerror("Erro ao Renomear", str(e), parent=self.root)
                self.undo()

    def _toggle_final_from_menu(self, state):
        self._push_undo_snapshot()
        if state in self.automato.final_states:
            self.automato.final_states.remove(state)
        else:
            self.automato.final_states.add(state)
        self.draw_all()

    def _delete_state_from_menu(self, state):
        if messagebox.askyesno("Excluir", f"Excluir o estado '{state}'?", parent=self.root):
            self._push_undo_snapshot()
            # A lógica de remoção de transições associadas deve estar na classe do autômato
            # self.automato.remove_state(state) 
            if state in self.positions:
                del self.positions[state]
            # Temporariamente, apenas removemos da GUI. A lógica completa de remoção
            # no modelo de dados precisa ser implementada em `pilha.py`.
            # A função rename_state já faz a remoção correta, então vamos usar uma lógica similar
            self.automato.remove_state(state) # Supondo que remove_state existe e funciona
            self.automato.states.discard(state)
            self.draw_all()

    def _edit_edge(self, src: str, dst: str):
        """Abre um diálogo para editar as transições entre dois estados."""
        # Agrega todas as transições existentes entre src e dst
        current_labels = []
        for (s, inp, pop), transitions in self.automato.transitions.items():
            if s != src: continue
            for d, push in transitions:
                if d == dst:
                    # Usamos 'or EPSILON' para garantir que não haja strings vazias
                    current_labels.append(f"{inp or EPSILON},{pop or EPSILON}/{push or EPSILON}")

        initial_value = "\n".join(current_labels)
        new_labels_str = simpledialog.askstring("Editar Transições",
            "Transições (uma por linha, formato: in, pop / push):",
            initialvalue=initial_value, parent=self.root)

        if new_labels_str is not None:
            self._push_undo_snapshot()
            # 1. Remove todas as transições antigas entre src e dst
            transitions_to_remove = []
            for key, destinations in self.automato.transitions.items():
                if key[0] == src:
                    # Filtra os destinos que não são para 'dst'
                    remaining_destinations = {d for d in destinations if d[0] != dst}
                    if len(remaining_destinations) < len(destinations):
                        transitions_to_remove.append((key, destinations - remaining_destinations))
            
            for key, to_remove in transitions_to_remove:
                self.automato.transitions[key] -= to_remove

            # Adiciona as novas transições
            for label in [line.strip() for line in new_labels_str.split('\n') if line.strip()]:
                if '/' in label:
                    read_part, push_part = label.split('/', 1)
                    input_sym, pop_sym = (read_part.split(',') + [EPSILON])[:2]
                    self.automato.add_transition(src, input_sym.strip(), pop_sym.strip(), dst, push_part.strip())
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
            if math.hypot(cx - sx, cy - cy) <= 24:
                return sid
        return None

    def _generate_svg_text(self):
        # Placeholder
        return '<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg"></svg>'

    def cmd_reset_sim(self):
        self.history = []
        self.sim_step = 0
        self.sim_playing = False
        self.result_indicator = None
        self.draw_all()
        self.status.config(text="Simulação reiniciada.")

    def draw_all(self):
        self.canvas.delete("all")
        
        # Desenha transições
        self._draw_simulation_display()
        self._draw_edges_and_states()

    def _draw_simulation_display(self):
        """Desenha a pilha e a fita de entrada restante no canvas inferior."""
        canvas = self.sim_display_canvas
        canvas.delete("all")
        
        if not self.history:
            return

        _, rem_input, stack = self.history[self.sim_step]

        # 1. Desenha a Pilha
        canvas.create_text(10, 25, text="Pilha:", anchor="w", font=("Helvetica", 10, "bold"))
        x_pos = 60
        cell_width, cell_height = 30, 30
        base_y = 50 # Linha de base para a pilha e a fita
        
        # Desenha a base da pilha
        canvas.create_line(x_pos - 5, base_y, x_pos + 10 * cell_width, base_y, width=2)

        for symbol in stack:
            canvas.create_rectangle(x_pos, base_y - cell_height, x_pos + cell_width, base_y, fill="#e0f2fe", outline="#7dd3fc")
            canvas.create_text(x_pos + cell_width/2, base_y - cell_height/2, text=symbol, font=("Courier", 12, "bold"))
            x_pos += cell_width

        # 2. Desenha a Entrada Restante
        tape_start_x = x_pos + 50
        canvas.create_text(tape_start_x, 25, text="Entrada Restante:", anchor="w", font=("Helvetica", 10, "bold"))
        
        input_to_show = rem_input or "&"
        x_pos = tape_start_x + 130
        
        # Cabeça de leitura
        canvas.create_polygon(x_pos + cell_width/2, base_y - cell_height - 5, x_pos + cell_width/2 - 5, base_y - cell_height - 15, x_pos + cell_width/2 + 5, base_y - cell_height - 15, fill="black")

        for i, symbol in enumerate(input_to_show):
            canvas.create_rectangle(x_pos, base_y - cell_height, x_pos + cell_width, base_y, fill="#f1f5f9", outline="#cbd5e1")
            canvas.create_text(x_pos + cell_width/2, base_y - cell_height/2, text=symbol, font=("Courier", 12, "bold"))
            x_pos += cell_width

    def _draw_edges_and_states(self):
        """Desenha os estados e as transições no canvas principal."""
        # Lógica para destacar transição ativa
        active_state = self.history[self.sim_step][0] if self.history else None
        prev_state = self.history[self.sim_step - 1][0] if self.history and self.sim_step > 0 else None
        input_str = self.input_entry.get()
        # Garante que o índice não saia do alcance da string de entrada
        input_char = input_str[self.sim_step - 1] if self.history and self.sim_step > 0 and self.sim_step <= len(input_str) else None

        agg = defaultdict(list)
        for (src, inp, pop), transitions in self.automato.transitions.items():
            for (dst, push) in transitions:
                label = f"{inp or EPSILON}, {pop or EPSILON} / {push or EPSILON}"
                agg[(src, dst)].append(label)

        for (src, dst), labels in agg.items():
            if src not in self.positions or dst not in self.positions: continue
            x1, y1 = self._from_canvas(*self.positions[src])
            x2, y2 = self._from_canvas(*self.positions[dst])

            # Verifica se alguma das transições nesta aresta está ativa
            is_active_transition = False
            if src == prev_state and dst == active_state:
                if any(f"{input_char or 'ε'}," in label for label in labels):
                    is_active_transition = True
            
            color = "#16a34a" if is_active_transition else "black"
            width = 3 if is_active_transition else 1.5
            
            display_labels = [label.replace(EPSILON, "ε") for label in labels]
            
            if src == dst:
                r = 24 * self.scale
                self.canvas.create_line(x1 - r*0.5, y1 - r*0.8, x1 - r*1.2, y1 - r*1.6, x1 + r*1.2, y1 - r*1.6, x1 + r*0.5, y1 - r*0.8, smooth=True, arrow=tk.LAST, width=width, fill=color)
                text_id = self.canvas.create_text(x1, y1 - r*1.8, text="\n".join(display_labels), fill=color, justify=tk.CENTER)
                self.canvas.tag_bind(text_id, "<Double-Button-1>", lambda e, s=src, d=dst: self._edit_edge(s, d))
            else:
                dx, dy = x2 - x1, y2 - y1
                dist = math.hypot(dx, dy)
                ux, uy = dx/dist, dy/dist
                
                bend = 0.25 if (dst, src) in agg else 0
                start_x, start_y = x1 + ux * 24 * self.scale, y1 + uy * 24 * self.scale
                end_x, end_y = x2 - ux * 24 * self.scale, y2 - uy * 24 * self.scale
                mid_x, mid_y = (start_x + end_x) / 2, (start_y + end_y) / 2
                ctrl_x, ctrl_y = mid_x - uy*dist*bend, mid_y + ux*dist*bend
                text_offset = 15
                txt_x, txt_y = mid_x - uy*(dist*bend*self.scale + text_offset), mid_y + ux*(dist*bend*self.scale + text_offset)

                self.canvas.create_line(start_x, start_y, ctrl_x, ctrl_y, end_x, end_y, smooth=True, arrow=tk.LAST, width=width, fill=color)
                text_id = self.canvas.create_text(txt_x, txt_y, text="\n".join(display_labels), fill=color, justify=tk.CENTER)
                self.canvas.tag_bind(text_id, "<Double-Button-1>", lambda e, s=src, d=dst: self._edit_edge(s, d))
                agg[(src, dst)] = {"text_pos": self._to_canvas(txt_x, txt_y)}

        # Desenha estados
        
        for sid in sorted(list(self.automato.states)):
            if sid not in self.positions: continue
            x_logic, y_logic = self.positions[sid]
            x, y = self._from_canvas(x_logic, y_logic)

            is_start = (sid == self.automato.start_state)
            is_final = (sid in self.automato.final_states)
            is_active = (sid == active_state)

            fill, outline, width = ("#e0f2fe", "#0284c7", 3) if is_active else ("white", "black", 2)
            
            self.canvas.create_oval(x-24*self.scale, y-24*self.scale, x+24*self.scale, y+24*self.scale, fill=fill, outline=outline, width=width)
            if is_final:
                self.canvas.create_oval(x-20*self.scale, y-20*self.scale, x+20*self.scale, y+20*self.scale, outline="black", width=1)
            self.canvas.create_text(x, y, text=sid)
            if is_start:
                self.canvas.create_line(x-48*self.scale, y, x-24*self.scale, y, arrow=tk.LAST)
        
        # Desenha o indicador de resultado final
        if self.result_indicator:
            color = "#16a34a" if self.result_indicator == "ACEITA" else "#dc2626"
            self.canvas.create_text(self.canvas.winfo_width() - 10, 20, text=self.result_indicator, 
                                    font=("Helvetica", 16, "bold"), fill=color, anchor="ne")

    # --- Métodos de Undo/Redo ---
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