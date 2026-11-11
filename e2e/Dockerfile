# Pruebas de extremo a extremo de RNF-20 (NF-02). Los navegadores viven solo en esta imagen:
# no se instala nada en el equipo.
# - Imagen oficial de Playwright 1.64.1: trae su Firefox (motor Gecko, con parches para automatizarlo).
# - Google Chrome y Microsoft Edge estables para Linux: se descargan de sus fuentes oficiales al
#   construir la imagen, así que son las versiones actuales de ese momento.
FROM mcr.microsoft.com/playwright:v1.64.1-noble

WORKDIR /e2e
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts && npx playwright install --with-deps chrome msedge
COPY . .

# Se ejecuta con el usuario del equipo (ver docker-compose.yml): HOME debe ser escribible.
ENV HOME=/tmp
CMD ["npx", "playwright", "test"]
