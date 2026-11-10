import { createRoot } from "react-dom/client";
import { DemoApp } from "./preview";
import "./preview.css";

createRoot(document.getElementById("root")!).render(<DemoApp />);
