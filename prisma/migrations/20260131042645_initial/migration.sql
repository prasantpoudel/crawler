-- CreateEnum
CREATE TYPE "Status" AS ENUM ('IN_PROGESS', 'FAILED', 'SUCESS');

-- CreateTable
CREATE TABLE "urls" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "website_name" TEXT NOT NULL,
    "desc" TEXT,
    "base_url" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3),

    CONSTRAINT "urls_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "scraping" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "base_url_id" UUID NOT NULL,
    "url" TEXT NOT NULL,
    "status" "Status",
    "page_hash" TEXT,
    "s3_key" TEXT,
    "depth" INTEGER DEFAULT 0,
    "error" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3),

    CONSTRAINT "scraping_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "urls_base_url_key" ON "urls"("base_url");

-- AddForeignKey
ALTER TABLE "scraping" ADD CONSTRAINT "scraping_base_url_id_fkey" FOREIGN KEY ("base_url_id") REFERENCES "urls"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
