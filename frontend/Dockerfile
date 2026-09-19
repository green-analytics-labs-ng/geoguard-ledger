FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# Run as the image's built-in non-root `node` user. Vite only needs to read the
# source and write its cache inside node_modules, so handing the workdir —
# including the installed dependencies and the anonymous /app/node_modules
# volume compose mounts — to that user is enough.
RUN chown -R node:node /app
USER node

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
