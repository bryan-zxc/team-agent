FROM node:24-alpine AS base

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# --------------- dev ---------------
FROM base AS dev

EXPOSE 3000
CMD ["npm", "run", "dev"]

# --------------- production build ---------------
FROM base AS build

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# --------------- production runner ---------------
FROM node:24-alpine AS production

WORKDIR /app

COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./
COPY --from=build /app/public ./public

EXPOSE 3000

CMD ["npm", "start"]
