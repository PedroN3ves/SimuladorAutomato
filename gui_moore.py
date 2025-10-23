#!/usr/bin/env python3
"""
gui_moore.py - Interface Tkinter para editar e simular Máquinas de Moore.
"""
import json
import math
import os
import tkinter as tk, tkinter.ttk as ttk
from tkinter import simpledialog, filedialog, messagebox
from typing import Dict, Tuple, List, DefaultDict

# Importações da máquina de Moore e utilitários
from maquina_moore import MaquinaMoore, EPSILON, snapshot_of_moore, restore_from_moore_snapshot

# Importações de PIL para imagens
from PIL import Image, ImageTk, ImageEnhance

STATE_RADIUS = 28 # Raio dos estados (um pouco maior para caber a saída)
FONT = ("Helvetica", 11)
ANIM_MS = 400 # Velocidade da animação (passo a passo)

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
        x = self.widget.winfo_pointerx() + 15
        y = self.widget.winfo_pointery() + 10

        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True) # Janela sem bordas
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(tw, text=self.text, justify='left',
                       background="#ffffe0", relief='solid', borderwidth=1,
                       font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tooltip(self, event):
        """ Esconde a janela do tooltip. """
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None

class MooreGUI:
    """ Classe principal da interface gráfica para Máquinas de Moore. """
    def __init__(self, root: tk.Toplevel):
        self.root = root
        root.title("Editor de Máquinas de Moore")
        root.state('zoomed') # Inicia maximizado

        # Configuração de estilo para os botões ttk
        style = ttk.Style()
        style.configure("TButton", padding=(15, 12))
        style.configure("Accent.TButton", padding=(15, 12))
        style.configure("TMenubutton", padding=(15, 12))

        # Dados da máquina e da interface
        self.moore_machine = MaquinaMoore()
        self.positions: Dict[str, Tuple[int, int]] = {}
        self.edge_widgets: Dict[Tuple[str, str], Dict] = {} # Armazena infos das arestas (para clique)
        self.mode = "select" # Modo atual (select, add_state, add_transition_src, etc.)
        self.transition_src = None # Estado de origem ao criar transição
        self.dragging = None # Informações sobre o estado sendo arrastado
        self.mode_buttons: Dict[str, tk.Widget] = {} # Dicionário de botões da toolbar
        self.pinned_mode = "select" # Modo que permanece ativo após clicar
        self.icons: Dict[str, ImageTk.PhotoImage] = {} # Ícones carregados

        # Histórico para Undo/Redo
        self.undo_stack: List[str] = []
        self.redo_stack: List[str] = []

        # Estado da simulação
        self.history: List[Tuple[str, str]] = [] # Histórico de (estado, saída_acumulada)
        self.sim_step = 0 # Passo atual da simulação
        self.sim_playing = False # Se a simulação está rodando automaticamente
        self.final_output_indicator = None # String da saída final a ser exibida

        # Transformação do canvas (zoom/pan)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_last = None # Última posição do mouse durante o pan
        self.current_filepath = None # Caminho do arquivo atual

        # Construção da interface
        self._build_toolbar()
        self._build_canvas()
        self._build_simulation_bar()
        self._build_statusbar()
        self._bind_events()

        self.root.after(100, self.center_view) # Centraliza após um pequeno delay
        self._push_undo_snapshot() # Salva estado inicial para undo
        self.draw_all() # Desenha tudo inicialmente

    def center_view(self):
         """ Centraliza a visualização no canvas (placeholder). """
         # A lógica real seria mais complexa com zoom/pan.
         self.draw_all()

    def _build_toolbar(self):
        """ Constrói a barra de ferramentas superior. """
        toolbar = tk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5, 10))

        # --- Menu Arquivo ---
        file_menu = tk.Menu(toolbar, tearoff=0)
        file_menu.add_command(label="Abrir...", command=self.cmd_open)
        file_menu.add_command(label="Salvar", command=self.cmd_save)
        file_menu.add_command(label="Salvar Como...", command=self.cmd_save_as)
        self._create_toolbar_menubutton(toolbar, "arquivo", "Arquivo", file_menu)
        ttk.Separator(toolbar, orient='vertical').pack(side=tk.LEFT, padx=8, fill='y')

        # --- Botões de Edição ---
        self._create_toolbar_button(toolbar, "novo_estado", "Novo Estado", self.cmd_add_state)
        self._create_toolbar_button(toolbar, "nova_transicao", "Nova Transição", self.cmd_add_transition)
        self._create_toolbar_button(toolbar, "definir_inicio", "Definir Início", self.cmd_set_start)
        self._create_toolbar_button(toolbar, "excluir_estado", "Excluir Estado", self.cmd_delete_state_mode)
        # --- NOVO BOTÃO ---
        self._create_toolbar_button(toolbar, "excluir_transicao", "Excluir Transição", self.cmd_delete_transition_mode)
        # ------------------
        ttk.Separator(toolbar, orient='vertical').pack(side=tk.LEFT, padx=8, fill='y')


        # --- Menu Exportar ---
        export_menu = tk.Menu(toolbar, tearoff=0)
        export_menu.add_command(label="Exportar para TikZ (.tex)", command=self.cmd_export_tikz)
        export_menu.add_command(label="Exportar para SVG (.svg)", command=self.cmd_export_svg)
        export_menu.add_command(label="Exportar para PNG (.png)", command=self.cmd_export_png)
        self._create_toolbar_menubutton(toolbar, "exportar", "Exportar", export_menu)

        # Rótulo indicando o modo atual (à direita)
        self.mode_label = ttk.Label(toolbar, text="Modo: Selecionar", font=("Helvetica", 11, "bold"))
        self.mode_label.pack(side=tk.RIGHT, padx=10)

    def _create_toolbar_menubutton(self, parent, icon_name, tooltip_text, menu):
        """ Cria um botão de menu na barra de ferramentas com ícone e tooltip. """
        icon_path = os.path.join("icons", f"{icon_name}.png")
        try:
            img = Image.open(icon_path).convert("RGBA") # Garante canal alfa
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(1.5)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.1)
            img = img.resize((40, 40), Image.Resampling.LANCZOS)
            self.icons[icon_name] = ImageTk.PhotoImage(img)
            button = ttk.Menubutton(parent, image=self.icons[icon_name])
        except FileNotFoundError:
            button = ttk.Menubutton(parent, text=tooltip_text)
            print(f"Aviso: Ícone não encontrado em '{icon_path}'. Usando texto.")

        button["menu"] = menu
        button.pack(side=tk.LEFT, padx=2)
        Tooltip(button, tooltip_text)
        self.mode_buttons[icon_name] = button # Adiciona para controle de estilo

    def _create_toolbar_button(self, parent, icon_name, tooltip_text, command):
        """ Cria um botão normal na barra de ferramentas com ícone e tooltip. """
        icon_path = os.path.join("icons", f"{icon_name}.png")
        try:
            img = Image.open(icon_path).convert("RGBA")
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(1.5)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.1)
            img = img.resize((40, 40), Image.Resampling.LANCZOS)
            self.icons[icon_name] = ImageTk.PhotoImage(img)
            button = ttk.Button(parent, image=self.icons[icon_name], command=command)
        except FileNotFoundError:
            button = ttk.Button(parent, text=tooltip_text, command=command)
            print(f"Aviso: Ícone não encontrado em '{icon_path}'. Usando texto.")

        button.pack(side=tk.LEFT, padx=2)
        self.mode_buttons[icon_name] = button
        Tooltip(button, tooltip_text)

        # Atualiza modo no hover, mas não fixa (pinned=False)
        button.bind("<Enter>", lambda e, m=icon_name: self._set_mode(m, pinned=False))
        # Volta ao modo fixado quando o mouse sai
        button.bind("<Leave>", lambda e: self._set_mode(self.pinned_mode, pinned=False))

    def _build_canvas(self):
        """ Constrói o canvas principal para desenhar o autômato. """
        self.canvas = tk.Canvas(self.root, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=0)

    def _build_simulation_bar(self):
        """ Constrói a barra inferior para controle da simulação. """
        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        ttk.Label(bottom, text="Entrada para Simulação:", font=("Helvetica", 10)).pack(side=tk.LEFT)
        self.input_entry = ttk.Entry(bottom, width=30, font=("Helvetica", 11))
        self.input_entry.pack(side=tk.LEFT, padx=6, ipady=5)

        ttk.Button(bottom, text="Simular", command=self.cmd_animate, style="Accent.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Passo", command=self.cmd_step).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Play/Pausar", command=self.cmd_play_pause).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom, text="Reiniciar", command=self.cmd_reset_sim).pack(side=tk.LEFT, padx=2)

        ttk.Separator(bottom, orient='vertical').pack(side=tk.LEFT, padx=8, fill='y')

        ttk.Label(bottom, text="Saída Gerada:", font=("Helvetica", 10)).pack(side=tk.LEFT)
        self.output_canvas = tk.Canvas(bottom, height=40, bg="white", highlightthickness=0)
        self.output_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    def _build_statusbar(self):
        """ Constrói a barra de status inferior. """
        self.status = tk.Label(self.root, text="Pronto", anchor="w", relief=tk.SUNKEN)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def _bind_events(self):
        """ Associa eventos do mouse e teclado às funções correspondentes. """
        self.canvas.bind("<Button-1>", self.on_canvas_click)       # Clique esquerdo
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)        # Arrastar com esquerdo
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release) # Soltar esquerdo
        self.canvas.bind("<Button-3>", self.on_right_click)        # Clique direito
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)      # Scroll (Windows/macOS)
        self.canvas.bind("<Button-4>", self.on_mousewheel)        # Scroll up (Linux)
        self.canvas.bind("<Button-5>", self.on_mousewheel)        # Scroll down (Linux)
        self.canvas.bind("<Button-2>", self.on_middle_press)      # Clique meio (pan)
        self.canvas.bind("<B2-Motion>", self.on_middle_drag)       # Arrastar com meio (pan)
        self.canvas.bind("<ButtonRelease-2>", self.on_middle_release) # Soltar meio (pan)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click) # Duplo clique esquerdo
        self.root.bind("<Control-z>", lambda e: self.undo())       # Ctrl+Z (Undo)
        self.root.bind("<Control-y>", lambda e: self.redo())       # Ctrl+Y (Redo)

    # --- Métodos de Controle de Modo ---
    def _update_mode_button_styles(self):
        """ Atualiza o estilo dos botões da toolbar para destacar o modo ativo (pinado). """
        for name, btn in self.mode_buttons.items():
            is_pinned = (name == self.pinned_mode.replace("_src", "").replace("_dst", ""))
            # Aplica estilo Accent.TButton se pinado, TButton caso contrário
            if isinstance(btn, (ttk.Button, ttk.Menubutton)):
                btn.config(style="Accent.TButton" if is_pinned else "TButton")

    def _set_mode(self, new_mode, pinned=False):
        """ Define o modo de operação atual (e opcionalmente o fixa). """
        if pinned:
            self.pinned_mode = new_mode # Atualiza o modo fixo

        self.mode = new_mode # Atualiza o modo atual (pode ser temporário, do hover)

        mode_map = {
            "select": "Modo: Selecionar", "add_state": "Modo: Adicionar Estado",
            "add_transition_src": "Modo: Adicionar Transição (Origem)",
            "add_transition_dst": "Modo: Adicionar Transição (Destino)",
            "set_start": "Modo: Definir Início",
            "delete_state": "Modo: Excluir Estado",
            "delete_transition": "Modo: Excluir Transição" # Novo texto
        }
        cursor_map = {
            "add_state": "crosshair", "add_transition_src": "hand2",
            "add_transition_dst": "hand2", "set_start": "hand2",
            "delete_state": "X_cursor",
            "delete_transition": "X_cursor" # Novo cursor
        }
        self.canvas.config(cursor=cursor_map.get(new_mode, "arrow"))
        self.mode_label.config(text=mode_map.get(new_mode, "Modo: Selecionar"))
        # A barra de status é atualizada pelas funções cmd_* específicas
        self._update_mode_button_styles() # Atualiza destaque visual dos botões


    # --- Funções de Comando (cmd_*) ---
    def cmd_add_state(self):
        self._set_mode("add_state", pinned=True)
        self.status.config(text="Clique no canvas para adicionar um estado.")

    def cmd_add_transition(self):
        self._set_mode("add_transition_src", pinned=True)
        self.transition_src = None # Limpa origem anterior
        self.status.config(text="Clique no estado de origem.")

    def cmd_set_start(self):
        self._set_mode("set_start", pinned=True)
        self.status.config(text="Clique em um estado para torná-lo inicial.")

    def cmd_delete_state_mode(self):
        self._set_mode("delete_state", pinned=True)
        self.status.config(text="Clique em um estado para excluí-lo.")

    # --- NOVO COMANDO ---
    def cmd_delete_transition_mode(self):
        """Ativa o modo de exclusão de transição."""
        self._set_mode("delete_transition", pinned=True)
        self.status.config(text="Clique no rótulo de uma transição para excluí-la.")
    # ------------------

    def cmd_open(self):
        """ Abre um arquivo de máquina de Moore (.json). """
        path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("Moore Machine Files", "*.json"), ("All files", "*.*")]
        )
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f: snapshot = f.read()
            self.moore_machine, self.positions = restore_from_moore_snapshot(snapshot)
            self.current_filepath = path
            self.root.title(f"Editor de Máquinas de Moore — {self.current_filepath}")
            self.undo_stack = [snapshot]; self.redo_stack.clear() # Reseta histórico
            self.draw_all(); self.center_view() # Redesenha e tenta centralizar
            self.status.config(text=f"Arquivo '{path}' carregado com sucesso.")
        except Exception as e:
            messagebox.showerror("Erro ao Abrir", f"Não foi possível carregar o arquivo:\n{e}", parent=self.root)

    def cmd_save(self):
        """ Salva a máquina no arquivo atual ou abre 'Salvar Como'. """
        if not self.current_filepath: self.cmd_save_as()
        else:
            try:
                with open(self.current_filepath, "w", encoding="utf-8") as f:
                    f.write(snapshot_of_moore(self.moore_machine, self.positions))
                self.status.config(text=f"Arquivo salvo em '{self.current_filepath}'.")
            except Exception as e:
                messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo:\n{e}", parent=self.root)

    def cmd_save_as(self):
        """ Abre diálogo para salvar a máquina em um novo arquivo. """
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Moore Machine Files", "*.json"), ("All files", "*.*")]
        )
        if not path: return
        self.current_filepath = path
        self.root.title(f"Editor de Máquinas de Moore — {self.current_filepath}")
        self.cmd_save() # Chama o save normal após definir o caminho

    # --- Comandos de Exportação ---
    def cmd_export_tikz(self):
        messagebox.showinfo("Exportar", "A exportação para TikZ ainda não foi implementada para Máquinas de Moore.", parent=self.root)

    def cmd_export_svg(self):
        path = filedialog.asksaveasfilename(defaultextension=".svg", filetypes=[("SVG files", "*.svg")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f: f.write(self._generate_svg_text())
                messagebox.showinfo("Exportar", f"SVG exportado para {path}", parent=self.root)
            except Exception as e:
                messagebox.showerror("Erro ao Exportar SVG", f"Não foi possível salvar o SVG:\n{e}", parent=self.root)


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
        # Placeholder - A implementação real geraria o SVG do autômato
        return '<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg"></svg>'

    # --- Comandos de Simulação ---
    def cmd_animate(self):
        """ Inicia a simulação visual passo a passo. """
        input_str = self.input_entry.get()
        if not self.moore_machine.start_state:
            messagebox.showwarning("Simular", "Defina um estado inicial.", parent=self.root)
            return

        self.history, _ = self.moore_machine.simulate_history(input_str)
        self.sim_step = 0
        self.sim_playing = False
        self.final_output_indicator = None # Limpa indicador de resultado
        self.status.config(text=f"Iniciando simulação para '{input_str}'. Passo 0 (inicial).")
        self.draw_all() # Desenha o estado inicial

    def cmd_step(self):
        """ Avança um passo na simulação. """
        if not self.history:
            self.status.config(text="Nenhuma simulação em andamento. Clique em 'Simular'.")
            return

        # Verifica se já está no último passo (ou além)
        if self.sim_step >= len(self.history) - 1:
            _, final_output = self.moore_machine.simulate_history(self.input_entry.get())
            self.final_output_indicator = final_output if final_output is not None else "TRAVOU"
            self.status.config(text="Fim da simulação.")
            self.draw_all() # Redesenha para mostrar o indicador final
            return

        # Avança para o próximo passo
        self.sim_step += 1
        self.status.config(text=f"Processando passo {self.sim_step}...")
        self.draw_all() # Redesenha com o estado atualizado

    def cmd_play_pause(self):
        """ Inicia ou pausa a reprodução automática da simulação. """
        if not self.history:
            self.status.config(text="Nenhuma simulação em andamento.")
            return

        self.sim_playing = not self.sim_playing
        if self.sim_playing:
            self.status.config(text="Reproduzindo...")
            # Se já terminou, reinicia para tocar de novo
            if self.sim_step >= len(self.history) - 1:
                self.cmd_reset_sim()
                self.cmd_animate() # Reinicia a simulação completa
            self._playback_step() # Inicia o loop de reprodução
        else:
            self.status.config(text="Pausado.")

    def _playback_step(self):
        """ Função recursiva para a reprodução automática. """
        if self.sim_playing and self.sim_step < len(self.history) - 1:
            self.cmd_step() # Executa um passo
            # Agenda a próxima chamada após ANIM_MS milissegundos
            self.root.after(ANIM_MS, self._playback_step)
        elif self.sim_playing: # Chegou ao fim durante a reprodução
            self.sim_playing = False # Para a reprodução
            self.cmd_step() # Executa o último passo para mostrar o resultado final
            self.status.config(text="Reprodução finalizada.")

    def cmd_reset_sim(self):
        """ Reinicia o estado da simulação. """
        self.history, self.sim_step, self.sim_playing, self.final_output_indicator = [], 0, False, None
        # self.input_entry.delete(0, tk.END) # Opcional: Limpar campo de entrada
        self.status.config(text="Simulação reiniciada.")
        self.draw_all() # Redesenha para limpar destaques e fita

    # --- Handlers de Eventos do Canvas ---
    def on_canvas_click(self, event):
        """ Processa cliques no canvas baseado no modo atual. """
        cx, cy = self._to_canvas(event.x, event.y) # Converte para coordenadas lógicas
        clicked_state = self._find_state_at(cx, cy)
        clicked_edge = self._find_edge_at(cx, cy) # Verifica clique na aresta

        # --- NOVO: LÓGICA DE EXCLUIR TRANSIÇÃO ---
        if self.mode == "delete_transition":
            if clicked_edge:
                self._delete_edge(*clicked_edge) # Chama a função de exclusão
                self._set_mode("select", pinned=True) # Volta ao modo de seleção
            else:
                self.status.config(text="Clique no rótulo de uma transição para excluí-la.")
            return # Finaliza o processamento do clique aqui
        # ----------------------------------------

        if self.mode == "add_state":
            state_name = f"q{len(self.moore_machine.states)}"
            output_sym = simpledialog.askstring("Saída do Estado", "Símbolo de saída para o novo estado:", parent=self.root)
            if output_sym is not None: # Se o usuário não cancelou
                self._push_undo_snapshot() # Salva antes de adicionar
                self.positions[state_name] = (cx, cy)
                self.moore_machine.add_state(state_name, output_sym.strip() or "?") # Usa '?' se vazio
                self.draw_all()
                self.status.config(text=f"Estado '{state_name}' adicionado com saída '{output_sym}'.")
            else:
                self.status.config(text="Criação de estado cancelada.")
            # Permite adicionar múltiplos estados sem resetar o modo
            return

        if self.mode == "delete_state":
            if clicked_state:
                if messagebox.askyesno("Excluir Estado", f"Tem certeza que deseja excluir o estado '{clicked_state}'?", parent=self.root):
                    self._push_undo_snapshot() # Salva antes
                    self.moore_machine.remove_state(clicked_state)
                    if clicked_state in self.positions: del self.positions[clicked_state]
                    self._set_mode("select", pinned=True) # Volta para seleção
                    self.draw_all()
                    self.status.config(text=f"Estado '{clicked_state}' excluído.")
            else:
                self.status.config(text="Clique sobre um estado para excluir.")
            return

        if self.mode == "add_transition_src":
            if clicked_state:
                self.transition_src = clicked_state
                self._set_mode("add_transition_dst", pinned=True) # Continua no modo de adicionar transição
                self.status.config(text=f"Origem '{clicked_state}'. Clique no destino.")
            else:
                self.status.config(text="Clique em um estado de origem válido.")
            return

        if self.mode == "add_transition_dst":
            if clicked_state:
                src, dst = self.transition_src, clicked_state
                inp = simpledialog.askstring("Transição", "Símbolo de entrada:", parent=self.root)
                if inp is not None: # Se não cancelou
                    inp_final = inp.strip() or EPSILON # Usa EPSILON se vazio
                    self._push_undo_snapshot() # Salva antes
                    self.moore_machine.add_transition(src, inp_final, dst)
                    self.draw_all()
                    self.status.config(text=f"Transição {src} --{inp_final}--> {dst} adicionada.")
                else:
                    self.status.config(text="Adição de transição cancelada.")
                self._set_mode("select", pinned=True) # Volta para seleção
                self.transition_src = None # Limpa origem
            else:
                self.status.config(text="Clique em um estado de destino válido.")
            return

        if self.mode == "set_start":
            if clicked_state:
                self._push_undo_snapshot() # Salva antes
                self.moore_machine.start_state = clicked_state
                self._set_mode("select", pinned=True) # Volta para seleção
                self.draw_all()
                self.status.config(text=f"Estado '{clicked_state}' definido como inicial.")
            else:
                self.status.config(text="Clique sobre um estado para defini-lo como inicial.")
            return

        # Modo 'select' ou clique fora de alvos
        if clicked_state:
            self.dragging = (clicked_state, cx, cy) # Inicia arrasto
        else:
            self.dragging = None # Clicou no vazio

    def on_canvas_drag(self, event):
        """ Move o estado selecionado ao arrastar o mouse. """
        if self.dragging:
            sid, ox, oy = self.dragging
            cx, cy = self._to_canvas(event.x, event.y)
            dx, dy = cx - ox, cy - oy
            x0, y0 = self.positions.get(sid, (cx, cy)) # Pega posição atual ou usa nova
            self.positions[sid] = (x0 + dx, y0 + dy)
            self.dragging = (sid, cx, cy) # Atualiza ponto de referência do arrasto
            self.draw_all() # Redesenha em tempo real

    def on_canvas_release(self, event):
        """ Finaliza o arrasto de um estado. """
        if self.dragging:
            self._push_undo_snapshot() # Salva o estado APÓS soltar
        self.dragging = None

    def on_right_click(self, event):
        """ Mostra o menu de contexto para estados ou arestas. """
        cx, cy = self._to_canvas(event.x, event.y)
        state = self._find_state_at(cx, cy)
        if state:
            self._show_state_context_menu(event, state)
            return
        edge = self._find_edge_at(cx, cy)
        if edge:
             self._show_edge_context_menu(event, *edge) # Desempacota src, dst

    def on_canvas_double_click(self, event):
        """ Abre o editor de transições ao dar duplo clique numa aresta. """
        cx, cy = self._to_canvas(event.x, event.y)
        edge = self._find_edge_at(cx, cy)
        if edge:
            self._edit_edge(edge[0], edge[1])

    # --- Métodos de Menu de Contexto e Ações ---
    def _show_state_context_menu(self, event, state):
        """ Cria e exibe o menu de contexto para um estado. """
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"Definir '{state}' como inicial", command=lambda s=state: self._set_start_state(s))
        menu.add_command(label="Renomear", command=lambda s=state: self._rename_state(s))
        menu.add_command(label="Editar Saída", command=lambda s=state: self._edit_state_output(s))
        menu.add_separator()
        menu.add_command(label=f"Excluir estado '{state}'", command=lambda s=state: self._delete_state(s))
        menu.tk_popup(event.x_root, event.y_root)

    def _show_edge_context_menu(self, event, src, dst):
        """ Cria e exibe o menu de contexto para uma aresta (transição). """
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Editar transições...", command=lambda s=src, d=dst: self._edit_edge(s, d))
        menu.add_separator()
        menu.add_command(label="Excluir todas as transições", command=lambda s=src, d=dst: self._delete_edge(s, d))
        menu.tk_popup(event.x_root, event.y_root)

    def _set_start_state(self, state):
        """ Define o estado como inicial (ação do menu). """
        self._push_undo_snapshot()
        self.moore_machine.start_state = state
        self.draw_all()
        self.status.config(text=f"Estado '{state}' definido como inicial.")

    def _delete_state(self, state):
        """ Exclui o estado (ação do menu). """
        if messagebox.askyesno("Excluir Estado", f"Tem certeza que deseja excluir o estado '{state}'?", parent=self.root):
            self._push_undo_snapshot()
            self.moore_machine.remove_state(state)
            if state in self.positions: del self.positions[state]
            self.draw_all()
            self.status.config(text=f"Estado '{state}' excluído.")

    def _rename_state(self, old_name: str):
        """ Renomeia o estado (ação do menu). """
        new_name = simpledialog.askstring("Renomear", f"Novo nome para '{old_name}':", initialvalue=old_name, parent=self.root)
        if new_name and new_name != old_name:
            try:
                self._push_undo_snapshot()
                self.moore_machine.rename_state(old_name, new_name)
                self.positions[new_name] = self.positions.pop(old_name) # Atualiza posição
                self.draw_all()
                self.status.config(text=f"Estado '{old_name}' renomeado para '{new_name}'.")
            except ValueError as e: # Captura erro se nome já existe
                messagebox.showerror("Erro ao Renomear", str(e), parent=self.root)
                self.undo() # Desfaz a tentativa

    def _edit_state_output(self, state: str):
        """ Edita o símbolo de saída de um estado (ação do menu). """
        current_output = self.moore_machine.output_function.get(state, "")
        new_output = simpledialog.askstring("Editar Saída", f"Símbolo de saída para '{state}':", initialvalue=current_output, parent=self.root)
        if new_output is not None: # Se não cancelou
            new_output_final = new_output.strip() or "?" # Usa '?' se vazio
            self._push_undo_snapshot()
            self.moore_machine.output_function[state] = new_output_final
            # Atualiza também o alfabeto de saída
            self.moore_machine.output_alphabet.add(new_output_final)
            self.draw_all()
            self.status.config(text=f"Saída do estado '{state}' atualizada para '{new_output_final}'.")

    # --- NOVO MÉTODO ---
    def _delete_edge(self, src, dst):
        """ Exclui TODAS as transições entre src e dst (ação do menu/modo). """
        if messagebox.askyesno("Excluir Transições", f"Tem certeza que deseja excluir TODAS as transições de '{src}' para '{dst}'?", parent=self.root):
            transitions_to_remove = []
            # Itera para encontrar as chaves (inputs) a serem removidas
            for (s, inp), d in self.moore_machine.transitions.items():
                if s == src and d == dst:
                    transitions_to_remove.append(inp)

            if transitions_to_remove:
                self._push_undo_snapshot() # Salva antes de remover
                for inp in transitions_to_remove:
                    key = (src, inp)
                    if key in self.moore_machine.transitions:
                        del self.moore_machine.transitions[key]
                self.draw_all()
                self.status.config(text=f"Transições de {src} para {dst} excluídas.")
            else:
                self.status.config(text="Nenhuma transição encontrada para excluir.")
    # ------------------

    def _edit_edge(self, src: str, dst: str):
        """ Edita os símbolos de entrada das transições entre src e dst. """
        transitions_to_edit = [] # Guarda os inputs atuais
        for (s, inp), d in self.moore_machine.transitions.items():
            if s == src and d == dst:
                transitions_to_edit.append(inp)

        initial_value = ", ".join(sorted([inp.replace(EPSILON, "ε") for inp in transitions_to_edit]))
        new_label_str = simpledialog.askstring("Editar Transições",
            f"Símbolos de entrada de '{src}' para '{dst}' (separados por vírgula, use ε para vazio):",
            initialvalue=initial_value, parent=self.root)

        if new_label_str is not None: # Se não cancelou
            self._push_undo_snapshot() # Salva antes

            # Remove as transições antigas entre src e dst
            for inp in transitions_to_edit:
                key = (src, inp)
                if key in self.moore_machine.transitions:
                    del self.moore_machine.transitions[key]

            # Adiciona as novas transições
            new_inputs = [s.strip().replace("ε", EPSILON) or EPSILON for s in new_label_str.split(',') if s.strip()]
            added_count = 0
            for inp in new_inputs:
                try:
                    # Verifica se já existe transição para este input (não deveria em Moore, mas por segurança)
                    if (src, inp) not in self.moore_machine.transitions:
                        self.moore_machine.add_transition(src, inp, dst)
                        added_count += 1
                except ValueError as e: # Captura erro de estado inválido (não deveria ocorrer aqui)
                     messagebox.showerror("Erro", f"Erro ao adicionar transição para '{inp}': {e}", parent=self.root)


            if added_count > 0 or len(transitions_to_edit) > 0: # Se houve alguma mudança
                self.draw_all()
                self.status.config(text=f"Transições entre {src} e {dst} atualizadas.")
            else:
                 self.status.config(text="Nenhuma alteração nas transições.")


    # --- Métodos de Transformação e Busca ---
    def _to_canvas(self, x, y): return (x - self.offset_x) / self.scale, (y - self.offset_y) / self.scale
    def _from_canvas(self, x, y): return x * self.scale + self.offset_x, y * self.scale + self.offset_y

    def _find_state_at(self, cx, cy):
        """ Encontra um estado nas coordenadas LÓGICAS (cx, cy). """
        for sid, (sx, sy) in self.positions.items():
            # Compara distância com o raio LÓGICO (não escalado)
            if math.hypot(sx - cx, sy - cy) <= STATE_RADIUS: return sid
        return None

    def _find_edge_at(self, cx, cy):
        """ Encontra o rótulo de uma aresta nas coordenadas LÓGICAS (cx, cy). """
        min_dist_sq_logic = (20 / self.scale)**2 / (self.scale**2) # Tolerância lógica ao quadrado
        found_edge = None
        current_min_dist = float('inf')

        for (src, dst), info in self.edge_widgets.items():
            tx_logic, ty_logic = info.get("text_pos", (None, None))
            if tx_logic is not None:
                dist_sq = (cx - tx_logic)**2 + (cy - ty_logic)**2
                # Compara com a tolerância convertida para coordenadas lógicas ao quadrado
                if dist_sq < min_dist_sq_logic and dist_sq < current_min_dist:
                     found_edge = (src, dst)
                     current_min_dist = dist_sq # Atualiza a menor distância encontrada

        return found_edge


    # --- Métodos de Desenho ---
    def _draw_output_tape(self):
        """ Desenha a fita de saída no canvas inferior. """
        self.output_canvas.delete("all")
        # Pega a saída acumulada até o passo ATUAL da simulação
        output_str = self.history[self.sim_step][1] if self.history and self.sim_step < len(self.history) else ""

        cell_width = 35
        cell_height = 35
        y_pos = (self.output_canvas.winfo_height() - cell_height) / 2 if self.output_canvas.winfo_height() > cell_height else 5
        x_pos = 10

        for char in output_str:
            self.output_canvas.create_rectangle(x_pos, y_pos, x_pos + cell_width, y_pos + cell_height,
                                                fill="#f0fdf4", outline="#86efac", width=1.5)
            self.output_canvas.create_text(x_pos + cell_width / 2, y_pos + cell_height / 2,
                                           text=char.replace(EPSILON, "ε"), font=("Courier", 16, "bold"), fill="#15803d")
            x_pos += cell_width + 5

    def draw_all(self):
        """ Redesenha todo o conteúdo do canvas principal. """
        self.canvas.delete("all")
        self.edge_widgets.clear() # Limpa dados de desenho das arestas

        active_state = self.history[self.sim_step][0] if self.history and self.sim_step < len(self.history) else None
        prev_state = self.history[self.sim_step - 1][0] if self.history and self.sim_step > 0 else None
        input_char = self.input_entry.get()[self.sim_step - 1] if self.history and self.sim_step > 0 and len(self.input_entry.get()) >= self.sim_step else None

        # Agrega transições por origem/destino para desenhar setas
        agg: DefaultDict[Tuple[str, str], List[str]] = DefaultDict(list)
        for (src, inp), dst in self.moore_machine.transitions.items():
            agg[(src, dst)].append(inp)

        # Desenha Arestas
        for (src, dst), labels in sorted(list(agg.items())):
            if src not in self.positions or dst not in self.positions: continue
            x1_logic, y1_logic = self.positions[src]
            x2_logic, y2_logic = self.positions[dst]
            x1, y1 = self._from_canvas(x1_logic, y1_logic)
            x2, y2 = self._from_canvas(x2_logic, y2_logic)

            label_text = ", ".join(sorted([lbl.replace(EPSILON, "ε") for lbl in labels]))
            width = 1.5 * self.scale # Largura da linha escalada

            # Determina se esta transição está ativa na simulação
            is_active_transition = (src == prev_state and dst == active_state and input_char in labels)
            color = "#16a34a" if is_active_transition else "black" # Verde se ativa, preto senão
            width = 3 * self.scale if is_active_transition else width # Mais grossa se ativa

            if src == dst: # Laço
                r = STATE_RADIUS * self.scale
                # Pontos de controle ajustados
                p1 = (x1 - r * 0.5, y1 - r * 0.8)
                c1 = (x1 - r * 1.5, y1 - r * 2.5)
                c2 = (x1 + r * 1.5, y1 - r * 2.5)
                p2 = (x1 + r * 0.5, y1 - r * 0.8)
                self.canvas.create_line(p1, c1, c2, p2, smooth=True, arrow=tk.LAST, width=width, fill=color)
                tx, ty = x1, y1 - r * 2.3 # Posição do texto acima
                text_id = self.canvas.create_text(tx, ty, text=label_text, font=FONT, fill=color)
                # Armazena posição lógica do texto
                tx_logic, ty_logic = self._to_canvas(tx, ty)
                self.edge_widgets[(src, dst)] = {"text_pos": (tx_logic, ty_logic)}
                self.canvas.tag_bind(text_id, "<Double-Button-1>", lambda e, s=src, d=dst: self._edit_edge(s, d))
            else: # Transição normal
                dx, dy = x2 - x1, y2 - y1; dist = math.hypot(dx, dy) or 1
                ux, uy = dx/dist, dy/dist
                bend = 0.25 if (dst, src) in agg else 0 # Curvatura se houver transição de volta
                # Pontos inicial/final na borda dos círculos (escalados)
                start_x, start_y = x1+ux*STATE_RADIUS*self.scale, y1+uy*STATE_RADIUS*self.scale
                end_x, end_y = x2-ux*STATE_RADIUS*self.scale, y2-uy*STATE_RADIUS*self.scale
                mid_x, mid_y = (start_x + end_x) / 2, (start_y + end_y) / 2
                ctrl_x, ctrl_y = mid_x - uy*dist*bend, mid_y + ux*dist*bend # Ponto de controle da curva
                text_offset_view = 15 # Deslocamento visual do texto
                # Posiciona o texto perto do ponto de controle, perpendicular à linha média
                txt_x, txt_y = ctrl_x - uy * text_offset_view, ctrl_y + ux * text_offset_view
                self.canvas.create_line(start_x, start_y, ctrl_x, ctrl_y, end_x, end_y, smooth=True, width=width, arrow=tk.LAST, fill=color)
                text_id = self.canvas.create_text(txt_x, txt_y, text=label_text, font=FONT, fill=color)
                # Armazena posição lógica do texto
                tx_logic, ty_logic = self._to_canvas(txt_x, txt_y)
                self.edge_widgets[(src, dst)] = {"text_pos": (tx_logic, ty_logic)}
                self.canvas.tag_bind(text_id, "<Double-Button-1>", lambda e, s=src, d=dst: self._edit_edge(s, d))

        # Desenha Estados
        for sid in sorted(list(self.moore_machine.states)):
            x_logic, y_logic = self.positions.get(sid, (100 + len(self.positions)*5, 100)) # Posição padrão se não existir
            x, y = self._from_canvas(x_logic, y_logic)
            output_sym = self.moore_machine.output_function.get(sid, '?')
            state_label = f"{sid}\n—\n{output_sym}" # Texto do estado (nome e saída)

            is_active = (sid == active_state)
            fill, outline, width = ("#e0f2fe", "#0284c7", 3) if is_active else ("white", "black", 2) # Destaque se ativo

            radius = STATE_RADIUS * self.scale # Raio escalado
            self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius, fill=fill, outline=outline, width=width)
            self.canvas.create_text(x, y, text=state_label, font=FONT, justify=tk.CENTER)

        # Seta Inicial
        if self.moore_machine.start_state and self.moore_machine.start_state in self.positions:
            sx_logic, sy_logic = self.positions[self.moore_machine.start_state]
            sx, sy = self._from_canvas(sx_logic, sy_logic)
            self.canvas.create_line(sx-STATE_RADIUS*2*self.scale, sy, sx-STATE_RADIUS*self.scale, sy, arrow=tk.LAST, width=2) # Seta antes do estado

        # Indicador de Saída Final
        if self.final_output_indicator is not None:
            color = "#059669" if self.final_output_indicator != "TRAVOU" else "#dc2626" # Verde ou vermelho
            text = f"Saída Final: {self.final_output_indicator.replace(EPSILON, 'ε')}"
            # Posiciona no canto superior direito
            self.canvas.create_text(self.canvas.winfo_width()-10, 20, text=text, font=("Helvetica", 14, "bold"), fill=color, anchor="e")

        # Desenha a fita de saída no canvas inferior
        self._draw_output_tape()


    # --- Métodos de Undo/Redo ---
    def _push_undo_snapshot(self):
        """ Salva o estado atual da máquina e posições para permitir undo. """
        snap = snapshot_of_moore(self.moore_machine, self.positions)
        # Evita salvar estados idênticos consecutivos no histórico
        if not self.undo_stack or self.undo_stack[-1] != snap:
            self.undo_stack.append(snap)
            if len(self.undo_stack) > 50: self.undo_stack.pop(0) # Limita o tamanho do histórico
            self.redo_stack.clear() # Limpa o histórico de redo ao fazer uma nova ação

    def undo(self, event=None):
        """ Desfaz a última ação. """
        if len(self.undo_stack) > 1: # Precisa ter pelo menos o estado atual e um anterior
            self.redo_stack.append(self.undo_stack.pop()) # Move estado atual para redo
            # Restaura o estado anterior do topo da pilha undo
            self.moore_machine, self.positions = restore_from_moore_snapshot(self.undo_stack[-1])
            self.draw_all() # Redesenha com o estado restaurado
            self.status.config(text="Desfeito.")
        else:
            self.status.config(text="Nada para desfazer.")

    def redo(self, event=None):
        """ Refaz a última ação desfeita. """
        if self.redo_stack:
            snap = self.redo_stack.pop() # Pega o último estado desfeito
            self.undo_stack.append(snap) # Adiciona de volta ao histórico undo
            self.moore_machine, self.positions = restore_from_moore_snapshot(snap)
            self.draw_all() # Redesenha com o estado refeito
            self.status.config(text="Refeito.")
        else:
            self.status.config(text="Nada para refazer.")