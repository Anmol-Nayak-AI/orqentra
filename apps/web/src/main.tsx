import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthenticationProvider } from "./auth/provider";
import { ApiError } from "./lib/api";
import { App } from "./App";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (attempt, error) =>
        attempt < 2 && (!(error instanceof ApiError) || error.status >= 500),
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthenticationProvider>
          <App />
        </AuthenticationProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
