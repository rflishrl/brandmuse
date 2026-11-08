import { ArrowLeft } from "lucide-react";
import type React from "react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";

export const NotFoundPage: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center gap-4 animate-in fade-in">
      <span className="text-4xl font-extrabold text-foreground font-mono">404</span>
      <h2 className="text-xl font-semibold">Page not found</h2>
      <p className="text-sm text-muted-foreground max-w-sm">
        The requested page does not exist. Please return to the assistant workspace.
      </p>
      <Button variant="default" className="gap-2 mt-2" asChild>
        <Link to="/">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Workspace</span>
        </Link>
      </Button>
    </div>
  );
};

export default NotFoundPage;
