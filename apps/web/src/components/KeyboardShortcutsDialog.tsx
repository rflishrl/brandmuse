import { Keyboard, X } from "lucide-react";
import type React from "react";
import { useEffect, useRef } from "react";

interface KeyboardShortcutsDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ShortcutItem {
  keys: string[];
  description: string;
  category: "Navigasi" | "Aksi Input" | "Umum";
}

const SHORTCUTS: ShortcutItem[] = [
  {
    keys: ["⌘ / Ctrl", "K"],
    description: "Fokus ke kolom prompt chat",
    category: "Navigasi",
  },
  {
    keys: ["⌘ / Ctrl", "B"],
    description: "Buka / tutup sidebar navigasi desktop",
    category: "Navigasi",
  },
  {
    keys: ["⌘ / Ctrl", "1–5"],
    description: "Pindah cepat tab (Ask, Rules, Campaign, Gallery, Docs)",
    category: "Navigasi",
  },
  {
    keys: ["Enter"],
    description: "Kirim pesan prompt (aman IME composition)",
    category: "Aksi Input",
  },
  {
    keys: ["Shift", "Enter"],
    description: "Buat baris baru pada teks pertanyaan",
    category: "Aksi Input",
  },
  {
    keys: ["Esc"],
    description: "Tutup modal, drawer, atau lightbox aktif",
    category: "Umum",
  },
  {
    keys: ["⌘ / Ctrl", "/"],
    description: "Tampilkan bantuan pintasan keyboard ini",
    category: "Umum",
  },
];

export const KeyboardShortcutsDialog: React.FC<KeyboardShortcutsDialogProps> = ({
  isOpen,
  onClose,
}) => {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (isOpen) {
      if (!dialog.open) {
        dialog.showModal();
      }
    } else {
      if (dialog.open) {
        dialog.close();
      }
    }
  }, [isOpen]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const handleCancel = (e: Event) => {
      e.preventDefault();
      onClose();
    };

    dialog.addEventListener("cancel", handleCancel);
    return () => dialog.removeEventListener("cancel", handleCancel);
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="shortcuts-dialog-title"
      className="p-0 rounded-2xl bg-surface text-foreground border border-border shadow-2xl backdrop:bg-black/60 backdrop:backdrop-blur-sm max-w-lg w-full m-auto animate-in fade-in zoom-in-95 duration-150"
      onClick={(e) => {
        if (e.target === dialogRef.current) {
          onClose();
        }
      }}
    >
      <div className="p-6 flex flex-col gap-5">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border pb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-foreground/5 text-foreground border border-border">
              <Keyboard className="w-5 h-5" aria-hidden="true" />
            </div>
            <div>
              <h3
                id="shortcuts-dialog-title"
                className="text-base font-semibold text-foreground tracking-tight"
              >
                Pintasan Keyboard (Keyboard Shortcuts)
              </h3>
              <p className="text-xs text-muted-foreground">
                Navigasi cepat dan kontrol efisien di BrandMuse
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition-colors cursor-pointer"
            aria-label="Tutup dialog"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Shortcuts list grouped by category */}
        <div className="flex flex-col gap-4 max-h-[60vh] overflow-y-auto pr-1">
          {(["Navigasi", "Aksi Input", "Umum"] as const).map((category) => {
            const items = SHORTCUTS.filter((s) => s.category === category);
            return (
              <div key={category} className="flex flex-col gap-2">
                <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  {category}
                </span>
                <div className="flex flex-col gap-1.5 rounded-xl bg-surface-user/50 p-2 border border-border/50">
                  {items.map((item) => (
                    <div
                      key={item.description}
                      className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-foreground/[0.03] transition-colors"
                    >
                      <span className="text-xs text-foreground font-medium">
                        {item.description}
                      </span>
                      <div className="flex items-center gap-1">
                        {item.keys.map((k) => (
                          <kbd
                            key={k}
                            className="px-2 py-0.5 text-[11px] font-mono font-medium rounded-md bg-surface border border-border shadow-xs text-foreground"
                          >
                            {k}
                          </kbd>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer tip */}
        <div className="pt-2 border-t border-border flex items-center justify-between text-[11px] text-muted-foreground">
          <span>
            Tekan <kbd className="px-1.5 py-0.5 rounded bg-surface border font-mono">Esc</kbd> untuk
            menutup
          </span>
          <span className="font-mono">BrandMuse Core UX</span>
        </div>
      </div>
    </dialog>
  );
};
