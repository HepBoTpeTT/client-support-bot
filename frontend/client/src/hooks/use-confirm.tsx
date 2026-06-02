import * as React from "react";
import ConfirmDialog from "@/components/ui/confirm-dialog";

type ConfirmOptions = {
  title?: React.ReactNode;
  description?: React.ReactNode;
  confirmText?: React.ReactNode;
  cancelText?: React.ReactNode;
  variant?: "default" | "destructive";
};

type ConfirmContextValue = (
  options?: ConfirmOptions
) => Promise<boolean>;

const ConfirmContext = React.createContext<ConfirmContextValue | null>(null);

type ConfirmState = {
  open: boolean;
  title?: React.ReactNode;
  description?: React.ReactNode;
  confirmText?: React.ReactNode;
  cancelText?: React.ReactNode;
  variant?: "default" | "destructive";
};

const initialState: ConfirmState = {
  open: false,
  title: "Подтвердите действие",
  description: "Это действие нельзя отменить.",
  confirmText: "Подтвердить",
  cancelText: "Отмена",
  variant: "default",
};

export function ConfirmProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [state, setState] = React.useState<ConfirmState>(initialState);
  const resolverRef = React.useRef<((value: boolean) => void) | null>(null);

  const confirm = React.useCallback((options: ConfirmOptions = {}) => {
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
      setState({
        open: true,
        title: options.title ?? initialState.title,
        description: options.description ?? initialState.description,
        confirmText: options.confirmText ?? initialState.confirmText,
        cancelText: options.cancelText ?? initialState.cancelText,
        variant: options.variant ?? initialState.variant,
      });
    });
  }, []);

  const closeWith = React.useCallback((value: boolean) => {
    resolverRef.current?.(value);
    resolverRef.current = null;
    setState((prev) => ({ ...prev, open: false }));
  }, []);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <ConfirmDialog
        open={state.open}
        title={state.title}
        description={state.description}
        confirmText={state.confirmText}
        cancelText={state.cancelText}
        variant={state.variant}
        onConfirm={() => closeWith(true)}
        onCancel={() => closeWith(false)}
      />
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const ctx = React.useContext(ConfirmContext);

  if (!ctx) {
    throw new Error("useConfirm must be used within ConfirmProvider");
  }

  return ctx;
}