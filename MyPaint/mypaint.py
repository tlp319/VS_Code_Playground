"""MyPaint - a simple MSPaint-style drawing app.

Layout: tool section (left), color palette (bottom), canvas (center).
Saves the canvas as a .gif file.
"""

import math
import random
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
from PIL import Image, ImageDraw, ImageTk

CANVAS_W, CANVAS_H = 800, 520
MAX_UNDO = 25

PALETTE = [
    "#000000", "#7f7f7f", "#880015", "#ed1c24", "#ff7f27", "#fff200",
    "#22b14c", "#00a2e8", "#3f48cc", "#a349a4", "#b97a57", "#ffaec9",
    "#ffffff", "#c3c3c3", "#b5e61d", "#99d9ea", "#7092be", "#c8bfe7",
    "#efe4b0", "#ffc90e", "#a8e61d", "#00b7ef", "#6f3198", "#ff0080",
]


class PaintApp:
    def __init__(self, root):
        self.root = root
        root.title("MyPaint")
        root.resizable(False, False)

        self.color = "#000000"
        self.bg_color = "#ffffff"
        self.tool = "pencil"
        self.size = 3
        self.start = None
        self.last = None
        self.temp_item = None
        self.undo_stack = []

        # PIL image is the source of truth; the canvas displays it.
        self.image = Image.new("RGB", (CANVAS_W, CANVAS_H), self.bg_color)
        self.draw = ImageDraw.Draw(self.image)

        self._build_ui()
        self._refresh_canvas()
        self._bind_events()

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        # Top bar: file actions
        top = tk.Frame(self.root, bd=1, relief=tk.RAISED, padx=4, pady=4)
        top.pack(side=tk.TOP, fill=tk.X)
        for text, cmd in (("New", self.new_canvas),
                          ("Save GIF", self.save_gif),
                          ("Undo (Ctrl+Z)", self.undo)):
            tk.Button(top, text=text, command=cmd, padx=8).pack(side=tk.LEFT, padx=2)

        body = tk.Frame(self.root)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Left: tools
        tools = tk.LabelFrame(body, text="Tools", padx=6, pady=6)
        tools.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)

        self.tool_buttons = {}
        tool_defs = [
            ("Pencil", "pencil"), ("Brush", "brush"), ("Eraser", "eraser"),
            ("Line", "line"), ("Rectangle", "rect"), ("Ellipse", "ellipse"),
            ("Star", "star"), ("Octagon", "octagon"), ("Diamond", "diamond"),
            ("Fill", "fill"), ("Picker", "picker"),
        ]
        for i, (label, name) in enumerate(tool_defs):
            b = tk.Button(tools, text=label, width=8,
                          command=lambda n=name: self.select_tool(n))
            b.grid(row=i // 2, column=i % 2, padx=2, pady=2)
            self.tool_buttons[name] = b

        tk.Label(tools, text="Size").grid(row=6, column=0, columnspan=2, pady=(10, 0))
        self.size_var = tk.IntVar(value=self.size)
        tk.Scale(tools, from_=1, to=40, orient=tk.HORIZONTAL, variable=self.size_var,
                 length=110).grid(row=7, column=0, columnspan=2)

        # Center: canvas
        canvas_frame = tk.Frame(body, bd=2, relief=tk.SUNKEN)
        canvas_frame.pack(side=tk.LEFT, padx=4, pady=4)
        self.canvas = tk.Canvas(canvas_frame, width=CANVAS_W, height=CANVAS_H,
                                bg="white", cursor="crosshair", highlightthickness=0)
        self.canvas.pack()

        # Bottom: color palette
        bottom = tk.LabelFrame(self.root, text="Colors", padx=6, pady=4)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=4)

        self.color_preview = tk.Canvas(bottom, width=36, height=36, bd=1,
                                       relief=tk.SUNKEN, highlightthickness=0)
        self.color_preview.pack(side=tk.LEFT, padx=(2, 10))
        self._update_color_preview()

        swatches = tk.Frame(bottom)
        swatches.pack(side=tk.LEFT)
        for i, c in enumerate(PALETTE):
            sw = tk.Canvas(swatches, width=18, height=18, bg=c, bd=1,
                           relief=tk.RAISED, highlightthickness=0)
            sw.grid(row=i // 12, column=i % 12, padx=1, pady=1)
            sw.bind("<Button-1>", lambda e, c=c: self.set_color(c))

        tk.Button(bottom, text="More...", command=self.pick_custom_color).pack(
            side=tk.LEFT, padx=10)

        self.select_tool("pencil")

    def _bind_events(self):
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Control-z>", lambda e: self.undo())

    # --------------------------------------------------------- helpers
    def select_tool(self, name):
        self.tool = name
        for n, b in self.tool_buttons.items():
            b.config(relief=tk.SUNKEN if n == name else tk.RAISED,
                     bg="#cde4ff" if n == name else "SystemButtonFace")

    def set_color(self, c):
        self.color = c
        self._update_color_preview()

    def pick_custom_color(self):
        c = colorchooser.askcolor(color=self.color, title="Choose color")
        if c and c[1]:
            self.set_color(c[1])

    def _update_color_preview(self):
        self.color_preview.delete("all")
        self.color_preview.create_rectangle(0, 0, 40, 40, fill=self.color, width=0)

    def _refresh_canvas(self):
        self.photo = ImageTk.PhotoImage(self.image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

    def _push_undo(self):
        self.undo_stack.append(self.image.copy())
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)

    def _clamp(self, x, y):
        return max(0, min(CANVAS_W - 1, x)), max(0, min(CANVAS_H - 1, y))

    def _active_color(self):
        return self.bg_color if self.tool == "eraser" else self.color

    # ----------------------------------------------------- mouse events
    def on_press(self, event):
        x, y = self._clamp(event.x, event.y)
        self.size = self.size_var.get()

        if self.tool == "picker":
            r, g, b = self.image.getpixel((x, y))[:3]
            self.set_color(f"#{r:02x}{g:02x}{b:02x}")
            return

        self._push_undo()

        if self.tool == "fill":
            ImageDraw.floodfill(self.image, (x, y), self._hex_to_rgb(self.color),
                                thresh=30)
            self._refresh_canvas()
            return

        self.start = (x, y)
        self.last = (x, y)
        if self.tool == "brush":
            self._make_bristles()
        if self.tool in ("pencil", "brush", "eraser"):
            self._stroke_to(x, y)

    def on_drag(self, event):
        if self.start is None:
            return
        x, y = self._clamp(event.x, event.y)

        if self.tool in ("pencil", "brush", "eraser"):
            self._stroke_to(x, y)
        elif self.tool in ("line", "rect", "ellipse", "star", "octagon", "diamond"):
            # live preview as a temporary canvas item
            if self.temp_item:
                self.canvas.delete(self.temp_item)
            x0, y0 = self.start
            w = max(1, self.size)
            if self.tool == "line":
                self.temp_item = self.canvas.create_line(x0, y0, x, y,
                                                         fill=self.color, width=w)
            elif self.tool == "rect":
                self.temp_item = self.canvas.create_rectangle(x0, y0, x, y,
                                                              outline=self.color, width=w)
            elif self.tool in ("star", "octagon", "diamond"):
                pts = self._poly_points(self.tool, x0, y0, x, y)
                self.temp_item = self.canvas.create_polygon(
                    pts, outline=self.color, fill="", width=w)
            else:
                self.temp_item = self.canvas.create_oval(x0, y0, x, y,
                                                         outline=self.color, width=w)

    def on_release(self, event):
        if self.start is None:
            return
        x, y = self._clamp(event.x, event.y)
        x0, y0 = self.start
        w = max(1, self.size)
        rgb = self._hex_to_rgb(self.color)

        if self.tool == "line":
            self.draw.line([x0, y0, x, y], fill=rgb, width=w)
            self._cap_round(x0, y0, w, rgb)
            self._cap_round(x, y, w, rgb)
        elif self.tool in ("rect", "ellipse"):
            box = [min(x0, x), min(y0, y), max(x0, x), max(y0, y)]
            if self.tool == "rect":
                self.draw.rectangle(box, outline=rgb, width=w)
            else:
                self.draw.ellipse(box, outline=rgb, width=w)
        elif self.tool in ("star", "octagon", "diamond"):
            pts = self._poly_points(self.tool, x0, y0, x, y)
            # closed outline; joint='curve' keeps thick corners clean
            self.draw.line(pts + pts[:2], fill=rgb, width=w, joint="curve")
            if w > 2:
                self._cap_round(pts[0], pts[1], w, rgb)

        self.start = None
        self.last = None
        self.temp_item = None
        self._refresh_canvas()

    def _stroke_to(self, x, y):
        if self.tool == "brush":
            self._brush_stroke(x, y)
            return
        lx, ly = self.last
        w = max(1, self.size)
        rgb = self._hex_to_rgb(self._active_color())
        self.draw.line([lx, ly, x, y], fill=rgb, width=w)
        if w > 2:
            self._cap_round(x, y, w, rgb)
        # echo onto the visible canvas for instant feedback
        self.canvas.create_line(lx, ly, x, y, fill=self._active_color(), width=w,
                                capstyle=tk.ROUND, smooth=True)
        self.last = (x, y)

    def _make_bristles(self):
        """Scatter bristles across the brush tip: each is (offset, opacity)."""
        radius = max(1.5, self.size / 2)
        count = max(12, int(self.size * 2.5))
        self.bristles = []
        for _ in range(count):
            # denser toward the center, sparser at the edges
            r = radius * math.sqrt(random.random())
            a = random.uniform(0, 2 * math.pi)
            dx, dy = r * math.cos(a), r * math.sin(a)
            edge = r / radius  # 0 center .. 1 edge
            alpha = int(random.uniform(170, 255) * (1.0 - 0.65 * edge))
            width = 2 if edge < 0.45 and self.size >= 6 else 1
            self.bristles.append((dx, dy, alpha, width))

    def _brush_stroke(self, x, y):
        lx, ly = self.last
        r, g, b = self._hex_to_rgb(self.color)
        pad = int(self.size) + 3
        bx0 = max(0, min(lx, x) - pad)
        by0 = max(0, min(ly, y) - pad)
        bx1 = min(CANVAS_W, max(lx, x) + pad)
        by1 = min(CANVAS_H, max(ly, y) + pad)

        # alpha-composite the bristle strands onto just the affected region
        overlay = Image.new("RGBA", (bx1 - bx0, by1 - by0), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for dx, dy, alpha, width in self.bristles:
            jx, jy = random.uniform(-0.8, 0.8), random.uniform(-0.8, 0.8)
            od.line([lx - bx0 + dx, ly - by0 + dy,
                     x - bx0 + dx + jx, y - by0 + dy + jy],
                    fill=(r, g, b, alpha), width=width)
        region = self.image.crop((bx0, by0, bx1, by1)).convert("RGBA")
        region.alpha_composite(overlay)
        self.image.paste(region.convert("RGB"), (bx0, by0))

        # light stippled echo on the visible canvas; the true render
        # replaces it when the stroke ends
        for dx, dy, alpha, width in self.bristles[::2]:
            self.canvas.create_line(lx + dx, ly + dy, x + dx, y + dy,
                                    fill=self.color, width=1, stipple="gray50")
        self.last = (x, y)

    def _cap_round(self, x, y, w, rgb):
        r = w / 2
        self.draw.ellipse([x - r, y - r, x + r, y + r], fill=rgb)

    @staticmethod
    def _poly_points(shape, x0, y0, x1, y1):
        """Flat [x, y, ...] vertex list for a shape fit to the drag box."""
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = abs(x1 - x0) / 2, abs(y1 - y0) / 2
        if shape == "star":
            inner = 0.382  # classic pentagram inner/outer radius ratio
            pts = []
            for i in range(10):
                ang = -math.pi / 2 + i * math.pi / 5  # top point up
                f = 1.0 if i % 2 == 0 else inner
                pts += [cx + f * rx * math.cos(ang), cy + f * ry * math.sin(ang)]
            return pts
        if shape == "diamond":
            return [cx, cy - ry, cx + rx, cy, cx, cy + ry, cx - rx, cy]
        # octagon: rectangle with corners cut so sides are equal when square
        k = 1 / (2 + math.sqrt(2))
        ox, oy = 2 * rx * k, 2 * ry * k
        left, right = cx - rx, cx + rx
        top, bot = cy - ry, cy + ry
        return [left + ox, top, right - ox, top, right, top + oy,
                right, bot - oy, right - ox, bot, left + ox, bot,
                left, bot - oy, left, top + oy]

    @staticmethod
    def _hex_to_rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    # ------------------------------------------------------- commands
    def new_canvas(self):
        if messagebox.askyesno("New", "Clear the canvas? Unsaved work will be lost."):
            self._push_undo()
            self.image.paste(self.bg_color, [0, 0, CANVAS_W, CANVAS_H])
            self._refresh_canvas()

    def undo(self):
        if self.undo_stack:
            self.image = self.undo_stack.pop()
            self.draw = ImageDraw.Draw(self.image)
            self._refresh_canvas()

    def save_gif(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".gif",
            filetypes=[("GIF image", "*.gif")],
            initialfile="drawing.gif",
            title="Save canvas as GIF")
        if not path:
            return
        try:
            self.image.convert("P", palette=Image.ADAPTIVE).save(path, format="GIF")
            messagebox.showinfo("Saved", f"Canvas saved to:\n{path}")
        except OSError as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")


def main():
    root = tk.Tk()
    PaintApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
