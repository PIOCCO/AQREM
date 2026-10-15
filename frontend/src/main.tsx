import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import RootErrorBoundary from "./components/ui/RootErrorBoundary";
import { APP_BUILD_ID } from "./lib/appBuildInfo";
import { PRODUCT_V1 } from "./lib/productV1";
import "./index.css";

document.documentElement.dataset.aqremUi = PRODUCT_V1 ? "v1" : "legacy";
document.documentElement.dataset.aqremBuild = APP_BUILD_ID;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RootErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </RootErrorBoundary>
  </React.StrictMode>,
);
