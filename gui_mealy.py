#!/usr/bin/env python3
"""
gui_mealy.py - Interface Tkinter para editar e simular Máquinas de Mealy.
"""
import json
import math
import os
import tkinter as tk, tkinter.ttk as ttk
from tkinter import simpledialog, filedialog, messagebox
from typing import Dict, Tuple, Set, List, DefaultDict

from maquina_mealy import MaquinaMealy, EPSILON

STATE_RADIUS = 24
from PIL import Image, ImageTk, ImageEnhance
FONT = ("Helvetica", 11)
ACTIVE_MODE_COLOR = "#dbeafe"
DEFAULT_BTN_COLOR = "SystemButtonFace"
ANIM_MS = 400 # Milissegundos por passo na animação

def snapshot_of_mealy(machine: MaquinaMealy, positions: Dict[str, Tuple[int, int]]):
    """Retorna JSON serializável representando o estado completo (máquina + posições)."""
    data = {
        "mealy_machine": json.loads(machine.to_json()),
        "positions": positions
    }
    return json.dumps(data, ensure_ascii=False)

def restore_from_mealy_snapshot(s: str):
    """Restaura uma máquina de Mealy e suas posições a partir de um snapshot JSON."""
    data = json.loads(s)
    machine = MaquinaMealy.from_json(json.dumps(data.get("mealy_machine", {})))
    positions = data.get("positions", {})
    return machine, positions

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


class MealyGUI:
    def __init__(self, root: tk.Toplevel):
        self.root = root
        root.title("Editor de Máquinas de Mealy")
        root.state('zoomed') # Inicia a janela maximizada

        # Estilo para aumentar o tamanho dos botões
        style = ttk.Style()
        # ***** MODIFICAÇÃO: Aumenta o padding dos botões *****
        style.configure("TButton", padding=(15, 12)) # Padding aumentado
        style.configure("Accent.TButton", padding=(15, 12)) # Padding aumentado
        style.configure("TMenubutton", padding=(15, 12)) # Padding aumentado
        # ******************************************************

        # Modelo de dados
        self.mealy_machine = MaquinaMealy()
        self.positions: Dict[str, Tuple[int, int]] = {}
        self.edge_widgets: Dict[Tuple[str, str], Dict] = {}
        self.mode = "select"
        self.transition_src = None
        self.dragging = None
        self.pinned_mode = "select"

        self.mode_buttons: Dict[str, tk.Button] = {}
        self.icons: Dict[str, ImageTk.PhotoImage] = {}

        # Undo/Redo
        self.undo_stack: List[str] = []
        self.redo_stack: List[str] = []

        # Estado da simulação
        self.history: List[Tuple[str, str]] = []
        self.sim_step = 0
        self.sim_playing = False
        self.final_output_indicator = None

        # Transform (zoom/pan)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_last = None
        self.current_filepath = None

        # Construção da UI
        self._build_toolbar()
        self._build_canvas()
        self._build_simulation_bar()
        self._build_statusbar()
        self._bind_events()

        # Adiciona um pequeno atraso para garantir que a janela tenha as dimensões corretas
        self.root.after(100, self.center_view)

        self.draw_all()
        self._push_undo_snapshot()
        self._update_mode_button_styles()

    def center_view(self):
        """Centraliza a visualização da máquina no canvas."""
        if not self.positions:
            # Se não houver estados, centraliza a visualização em um ponto padrão
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            # Para Mealy, não há zoom/pan, então apenas garantimos que o primeiro estado
            # seja adicionado em um local razoável. A centralização real
            # aconteceria se implementássemos zoom/pan como no outro editor.
            # Por enquanto, esta função serve como um placeholder para futuras melhorias.
            pass

        # Redesenha para garantir que tudo esteja atualizado após o dimensionamento inicial
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
        self._create_toolbar_button(toolbar, "excluir_estado", "Excluir Estado", self.cmd_delete_state_mode)

        # --- Menu Exportar ---
        export_menu = tk.Menu(toolbar, tearoff=0)
        export_menu.add_command(label="Exportar para TikZ (.tex)", command=self.cmd_export_tikz)
        export_menu.add_command(label="Exportar para SVG (.svg)", command=self.cmd_export_svg)
        export_menu.add_command(label="Exportar para PNG (.png)", command=self.cmd_export_png)
        self._create_toolbar_menubutton(toolbar, "exportar", "Exportar", export_menu)

        ttk.Separator(toolbar, orient='vertical').pack(side=tk.LEFT, padx=8, fill='y')

        ttk.Button(toolbar, text="Simulação Rápida", command=self.cmd_quick_simulate).pack(side=tk.LEFT, padx=2)

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
            # ***** MODIFICAÇÃO: Aumenta o tamanho do ícone *****
            img = img.resize((40, 40), Image.Resampling.LANCZOS) # Tamanho aumentado para 40x40
            # ***************************************************
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
            # ***** MODIFICAÇÃO: Aumenta o tamanho do ícone *****
            img = img.resize((40, 40), Image.Resampling.LANCZOS) # Tamanho aumentado para 40x40
            # ***************************************************
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
        self.canvas = tk.Canvas(self.root, width=1000, height=600, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=0)

    def _build_simulation_bar(self):
        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        ttk.Label(bottom, text="Entrada para Simulação:", font=("Helvetica", 10)).pack(side=tk.LEFT)
        self.input_entry = ttk.Entry(bottom, width=30, font=("Helvetica", 11)) # Fonte um pouco maior na entrada
        self.input_entry.pack(side=tk.LEFT, padx=6, ipady=5) # ipady para aumentar a altura da caixa de entrada

        # ***** MODIFICAÇÃO: Botões de simulação agora usam o estilo ttk configurado *****
        ttk.Button(bottom, text="Simular", command=self.cmd_animate, style="Accent.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Passo", command=self.cmd_step).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Play/Pausar", command=self.cmd_play_pause).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Reiniciar", command=self.cmd_reset_sim).pack(side=tk.LEFT, padx=2)
        # ********************************************************************************

        ttk.Separator(bottom, orient='vertical').pack(side=tk.LEFT, padx=8, fill='y')

        ttk.Label(bottom, text="Saída Gerada:", font=("Helvetica", 10)).pack(side=tk.LEFT)
        # Canvas para desenhar a fita de saída
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
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())


    def _update_mode_button_styles(self):
        # O estilo de destaque reflete o modo PINADO (fixo)
        for mode_name, button in self.mode_buttons.items():
            is_pinned = (mode_name == self.pinned_mode.replace("_src", "").replace("_dst", ""))
            if is_pinned:
                button.config(style="Accent.TButton") # Estilo de destaque para o botão ativo
            else:
                button.config(style="TButton") # Estilo padrão

    def _set_mode(self, new_mode, pinned=False):
        if pinned:
            self.pinned_mode = new_mode

        self.mode = new_mode
        mode_text_map = {
            "select": "Modo: Selecionar",
            "add_state": "Modo: Adicionar Estado",
            "add_transition_src": "Modo: Adicionar Transição (Origem)",
            "add_transition_dst": "Modo: Adicionar Transição (Destino)",
            "set_start": "Modo: Definir Início",
            "delete_state": "Modo: Excluir Estado",
        }
        cursor_map = {
            "add_state": "crosshair",
            "add_transition_src": "hand2",
            "add_transition_dst": "hand2",
            "set_start": "hand2",
        }
        cursor_map["delete_state"] = "X_cursor"
        self.canvas.config(cursor=cursor_map.get(new_mode, "arrow"))
        self.mode_label.config(text=mode_text_map.get(new_mode, "Modo: Selecionar"))
        self.status.config(text=mode_text_map.get(new_mode, ""))
        self._update_mode_button_styles()

    def cmd_add_state(self): self._set_mode("add_state", pinned=True)
    def cmd_add_transition(self): self._set_mode("add_transition_src", pinned=True)
    def cmd_set_start(self): self._set_mode("set_start", pinned=True)

    def cmd_delete_state_mode(self):
        self._set_mode("delete_state", pinned=True)
        self.status.config(text="Clique em um estado para excluí-lo.")

    def cmd_open(self):
        """Abre um arquivo de Máquina de Mealy (.json)."""
        path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("Mealy Machine Files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                snapshot = f.read()
            self.mealy_machine, self.positions = restore_from_mealy_snapshot(snapshot)
            self.current_filepath = path
            self.root.title(f"Editor de Máquinas de Mealy — {self.current_filepath}")
            self.draw_all()
            self.status.config(text=f"Arquivo '{path}' carregado com sucesso.")
        except Exception as e:
            messagebox.showerror("Erro ao Abrir", f"Não foi possível carregar o arquivo:\n{e}", parent=self.root)

    def cmd_save(self):
        """Salva a máquina no arquivo atual. Se não houver, chama 'Salvar Como'."""
        if not self.current_filepath:
            self.cmd_save_as()
        else:
            try:
                with open(self.current_filepath, "w", encoding="utf-8") as f:
                    f.write(snapshot_of_mealy(self.mealy_machine, self.positions))
                self.status.config(text=f"Arquivo salvo em '{self.current_filepath}'.")
            except Exception as e:
                messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo:\n{e}", parent=self.root)

    def cmd_save_as(self):
        """Abre um diálogo para salvar a máquina em um novo arquivo."""
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Mealy Machine Files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        self.current_filepath = path
        self.root.title(f"Editor de Máquinas de Mealy — {self.current_filepath}")
        self.cmd_save()

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

    def cmd_export_tikz(self):
        messagebox.showinfo("Exportar", "A exportação para TikZ ainda não foi implementada para Máquinas de Mealy.", parent=self.root)

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

    def _generate_svg_text(self):
        # Placeholder
        return '<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg"></svg>'

    def on_canvas_click(self, event):
        cx, cy = self._to_canvas(event.x, event.y)
        if self.mode == "add_state":
            sid = f"q{len(self.mealy_machine.states)}"
            self.mealy_machine.add_state(sid)
            self._push_undo_snapshot()
            self.positions[sid] = (cx, cy)
            self.draw_all()
            return

        clicked_state = self._find_state_at(cx, cy)

        if self.mode == "delete_state":
            if clicked_state:
                if messagebox.askyesno("Excluir", f"Excluir estado {clicked_state}?", parent=self.root):
                    self._push_undo_snapshot()
                    self.mealy_machine.remove_state(clicked_state)
                    if clicked_state in self.positions: del self.positions[clicked_state]
                    self._set_mode("select", pinned=True)
                    self.draw_all()
            return

        if self.mode == "add_transition_src" and clicked_state:
            self.transition_src = clicked_state
            self._set_mode("add_transition_dst", pinned=True)
            self.status.config(text=f"Origem {clicked_state} selecionada. Clique no destino.")
            return

        if self.mode == "add_transition_dst" and clicked_state:
            src = self.transition_src
            dst = clicked_state
            label = simpledialog.askstring("Transição", "Digite a transição no formato 'entrada/saída':", parent=self.root)
            try:
                if label and '/' in label:
                    inp, outp = label.split('/', 1)
                    self.mealy_machine.add_transition(src, inp.strip(), dst, outp.strip())
                    self._push_undo_snapshot()
                    self.draw_all()
            except (ValueError, IndexError) as e:
                messagebox.showerror("Erro de Formato", f"Formato de transição inválido. Use 'entrada/saída'.\n\nDetalhe: {e}", parent=self.root)
            self._set_mode("select", pinned=True)
            return

        if self.mode == "set_start" and clicked_state:
            self._push_undo_snapshot()
            self.mealy_machine.start_state = clicked_state
            self._set_mode("select", pinned=True)
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
        if self.dragging: self._push_undo_snapshot()
        self.dragging = None

    def on_right_click(self, event):
        cx, cy = self._to_canvas(event.x, event.y)
        state = self._find_state_at(cx, cy)
        if state:
            self._show_state_context_menu(event, state)
            return
        edge = self._find_edge_at(cx, cy)
        if edge:
            self._show_edge_context_menu(event, edge[0], edge[1])

    def on_canvas_double_click(self, event):
        """Handles double-clicks on the canvas to edit transitions."""
        cx, cy = self._to_canvas(event.x, event.y)
        edge = self._find_edge_at(cx, cy)
        if edge:
            self._edit_edge(edge[0], edge[1])

    def _show_state_context_menu(self, event, state):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"Definir '{state}' como inicial", command=lambda: self._set_start_state(state))
        menu.add_command(label="Renomear", command=lambda: self._rename_state(state))
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
        self._push_undo_snapshot()
        self.mealy_machine.start_state = state
        self.draw_all()

    def _delete_state(self, state):
        if messagebox.askyesno("Excluir Estado", f"Tem certeza que deseja excluir o estado '{state}' e todas as suas transições?", parent=self.root):
            self._push_undo_snapshot()
            self.mealy_machine.remove_state(state)
            if state in self.positions:
                del self.positions[state]
            self.draw_all()

    def _rename_state(self, old_name: str):
        """Abre um diálogo para renomear um estado."""
        new_name = simpledialog.askstring("Renomear Estado", f"Digite o novo nome para '{old_name}':",
                                          initialvalue=old_name, parent=self.root)

        if new_name and new_name != old_name:
            try:
                self._push_undo_snapshot()
                self.mealy_machine.rename_state(old_name, new_name)
                # Atualiza o dicionário de posições
                self.positions[new_name] = self.positions.pop(old_name)
                self.draw_all()
                self.status.config(text=f"Estado '{old_name}' renomeado para '{new_name}'.")
            except ValueError as e:
                messagebox.showerror("Erro ao Renomear", str(e), parent=self.root)
                self.undo()

    def _delete_edge(self, src, dst):
        if messagebox.askyesno("Excluir Transições", f"Tem certeza que deseja excluir TODAS as transições de '{src}' para '{dst}'?", parent=self.root):
            transitions_to_remove = []
            for (s, inp), (d, outp) in self.mealy_machine.transitions.items():
                if s == src and d == dst:
                    self._push_undo_snapshot()
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
            self._push_undo_snapshot()
            for inp in transitions_to_edit:
                self.mealy_machine.remove_transition(src, inp)
            new_labels = [label.strip() for label in new_label_str.split(',')]
            try:
                for label in new_labels:
                    if '/' in label:
                        inp, outp = label.split('/', 1)
                        self.mealy_machine.add_transition(src, inp.strip(), dst, outp.strip())
            except (ValueError, IndexError) as e:
                 messagebox.showerror("Erro de Formato", f"Formato de transição inválido. Use 'in/out'.\n\nDetalhe: {e}", parent=self.root)
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
        for (src, dst), info in self.edge_widgets.items():
            tx, ty = info.get("text_pos", (0,0))
            if tx and math.hypot(tx - cx, ty - cy) <= 20: return src, dst
        return None

    def _draw_output_tape(self):
        """Desenha a fita de saída gerada no canvas."""
        self.output_canvas.delete("all")

        # Pega a string de saída do passo atual do histórico
        output_str = self.history[self.sim_step][1] if self.history and self.sim_step >= 0 else "" # Adjusted index check

        cell_width = 35
        cell_height = 35
        # Centraliza verticalmente no canvas
        y_pos = (self.output_canvas.winfo_height() / 2) - (cell_height / 2) if self.output_canvas.winfo_height() > cell_height else 5
        x_pos = 10

        for char in output_str:
            # Desenha a caixa
            self.output_canvas.create_rectangle(x_pos, y_pos, x_pos + cell_width, y_pos + cell_height,
                                                fill="#f0fdf4", outline="#86efac", width=1.5)
            # Desenha o caractere de saída
            self.output_canvas.create_text(x_pos + cell_width / 2, y_pos + cell_height / 2,
                                           text=char, font=("Courier", 16, "bold"), fill="#15803d")
            x_pos += cell_width + 5 # Adiciona um pequeno espaço entre as caixas

    def draw_all(self):
        self.canvas.delete("all")
        self.edge_widgets.clear()

        # Desenho das transições
        agg: DefaultDict[Tuple[str, str], List[str]] = DefaultDict(list)
        for (src, inp), (dst, outp) in self.mealy_machine.transitions.items():
            agg[(src, dst)].append(f"{inp}/{outp}")

        for (src, dst), labels in sorted(list(agg.items())):
            if src not in self.positions or dst not in self.positions: continue
            x1, y1 = self._from_canvas(*self.positions[src])
            x2, y2 = self._from_canvas(*self.positions[dst])
            label_text = ", ".join(sorted(labels)).replace(EPSILON, "ε")

            if src == dst:
                p1 = (x1 - STATE_RADIUS * 0.7, y1 - STATE_RADIUS * 0.7)
                c1 = (x1 - STATE_RADIUS * 1.5, y1 - STATE_RADIUS * 2.5)
                c2 = (x1 + STATE_RADIUS * 1.5, y1 - STATE_RADIUS * 2.5)
                p2 = (x1 + STATE_RADIUS * 0.7, y1 - STATE_RADIUS * 0.7)
                self.canvas.create_line(p1, c1, c2, p2, smooth=True, arrow=tk.LAST, width=1.5 * self.scale)
                tx, ty = x1, y1 - STATE_RADIUS * 2.2 * self.scale
                text_id = self.canvas.create_text(tx, ty, text=label_text, font=FONT)
                self.edge_widgets[(src, dst)] = {"text_pos": self._to_canvas(tx, ty)}
                self.canvas.tag_bind(text_id, "<Double-Button-1>", lambda e, s=src, d=dst: self._edit_edge(s, d))
            else:
                dx, dy = x2 - x1, y2 - y1; dist = math.hypot(dx, dy) or 1
                ux, uy = dx/dist, dy/dist
                bend = 0.25 if (dst, src) in agg else 0
                start_x, start_y = x1 + ux * STATE_RADIUS * self.scale, y1 + uy * STATE_RADIUS * self.scale
                end_x, end_y = x2 - ux * STATE_RADIUS * self.scale, y2 - uy * STATE_RADIUS * self.scale
                mid_x, mid_y = (start_x + end_x) / 2, (start_y + end_y) / 2
                ctrl_x, ctrl_y = mid_x - uy*dist*bend, mid_y + ux*dist*bend
                text_offset = 15
                txt_x, txt_y = mid_x - uy*(dist*bend*self.scale + text_offset), mid_y + ux*(dist*bend*self.scale + text_offset)
                self.canvas.create_line(start_x, start_y, ctrl_x, ctrl_y, end_x, end_y, smooth=True, width=1.5 * self.scale, arrow=tk.LAST)
                text_id = self.canvas.create_text(txt_x, txt_y, text=label_text, font=FONT)
                self.edge_widgets[(src, dst)] = {"text_pos": self._to_canvas(txt_x, txt_y)}
                self.canvas.tag_bind(text_id, "<Double-Button-1>", lambda e, s=src, d=dst: self._edit_edge(s, d))

        # Desenho dos estados
        active_state = self.history[self.sim_step][0] if self.history else None
        for sid in sorted(list(self.mealy_machine.states)):
            x_logic, y_logic = self.positions.get(sid, (100, 100))
            x, y = self._from_canvas(x_logic, y_logic)
            is_active = (sid == active_state)
            fill, outline, width = ("#e0f2fe", "#0284c7", 3) if is_active else ("white", "black", 2)
            self.canvas.create_oval(x-STATE_RADIUS*self.scale, y-STATE_RADIUS*self.scale, x+STATE_RADIUS*self.scale, y+STATE_RADIUS*self.scale, fill=fill, outline=outline, width=width)
            self.canvas.create_text(x, y, text=sid, font=FONT)

        # Seta inicial
        if self.mealy_machine.start_state and self.mealy_machine.start_state in self.positions:
            sx_logic, sy_logic = self.positions[self.mealy_machine.start_state]
            sx, sy = self._from_canvas(sx_logic, sy_logic)
            self.canvas.create_line(sx-STATE_RADIUS*2*self.scale, sy, sx-STATE_RADIUS*self.scale, sy, arrow=tk.LAST, width=2)

        # Indicador de saída final
        if self.final_output_indicator is not None:
            color = "#059669" if self.final_output_indicator != "TRAVOU" else "#dc2626"
            text = f"Saída Final: {self.final_output_indicator}"
            self.canvas.create_text(self.canvas.winfo_width()-10, 20, text=text, font=("Helvetica", 14, "bold"), fill=color, anchor="e")

        # Desenha a fita de saída
        self._draw_output_tape()

    # --- Métodos de Simulação ---

    def cmd_animate(self):
        input_str = self.input_entry.get()
        self.history, final_output = self.mealy_machine.simulate_history(input_str)

        self.sim_step = 0 # Start from the initial state display
        self.sim_playing = False
        self.final_output_indicator = None # Limpa o indicador do canvas
        self.status.config(text=f"Iniciando simulação para a entrada '{input_str}'.")
        self.draw_all()

    def cmd_step(self):
        if not self.history:
            self.status.config(text="Nenhuma simulação em andamento. Clique em 'Simular' primeiro.")
            return

        # Verifica se está no último passo
        if self.sim_step >= len(self.history) - 1:
            _, final_output = self.mealy_machine.simulate_history(self.input_entry.get())
            self.final_output_indicator = final_output if final_output is not None else "TRAVOU"
            self.status.config(text="Fim da simulação.")
            self.draw_all()
            return

        self.sim_step += 1
        self.status.config(text=f"Processando passo {self.sim_step}...")
        self.draw_all()

    def cmd_play_pause(self):
        if not self.history:
            self.status.config(text="Nenhuma simulação em andamento. Clique em 'Simular' primeiro.")
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
        self.status.config(text="Simulação reiniciada.")
        self.draw_all()

    # --- Métodos de Undo/Redo ---
    def _push_undo_snapshot(self):
        snap = snapshot_of_mealy(self.mealy_machine, self.positions)
        if not self.undo_stack or self.undo_stack[-1] != snap:
            self.undo_stack.append(snap)
            if len(self.undo_stack) > 50: self.undo_stack.pop(0)
            self.redo_stack.clear()

    def undo(self, event=None):
        if len(self.undo_stack) > 1:
            self.redo_stack.append(self.undo_stack.pop())
            self.mealy_machine, self.positions = restore_from_mealy_snapshot(self.undo_stack[-1])
            self.draw_all(); self.status.config(text="Desfeito.")
        else: self.status.config(text="Nada para desfazer.")

    def redo(self, event=None):
        if self.redo_stack:
            snap = self.redo_stack.pop()
            self.undo_stack.append(snap)
            self.mealy_machine, self.positions = restore_from_mealy_snapshot(snap)
            self.draw_all(); self.status.config(text="Refeito.")
        else: self.status.config(text="Nada para refazer.")