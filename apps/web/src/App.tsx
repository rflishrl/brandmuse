import React from "react";
import { RouterProvider } from "react-router";
import { router } from "@/router";

export const App: React.FC = () => {
  return <RouterProvider router={router} />;
};

export default App;
