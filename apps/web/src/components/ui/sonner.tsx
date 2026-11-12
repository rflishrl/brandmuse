import type React from "react";
import { Toaster as SonnerToaster } from "sonner";

export const Toaster: React.FC = () => {
  return (
    <SonnerToaster
      position="bottom-right"
      closeButton
      richColors
      expand
      toastOptions={{
        duration: 4000,
        className: "font-sans text-xs sm:text-sm border shadow-lg rounded-2xl backdrop-blur-md",
      }}
    />
  );
};

export { toast } from "sonner";
