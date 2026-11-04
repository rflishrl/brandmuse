import { defineConfig } from "orval";

export default defineConfig({
  brandmuse: {
    input: "./openapi.json",
    output: {
      mode: "split",
      target: "./src/api/generated.ts",
      schemas: "./src/api/model",
      client: "react-query",
      mock: false,
      override: {
        mutator: {
          path: "./src/api/mutator.ts",
          name: "customInstance",
        },
        query: {
          useQuery: true,
          useMutation: true,
        },
      },
    },
  },
});
