import asyncio
from prisma import Prisma

async def main():
    db = Prisma()
    await db.connect()

    print("Seeding database...")
    
    # Check if we already have a url
    existing = await db.urls.find_first(where={"BaseUrl": "https://docs.stripe.com/api/"})
    
    if not existing:
        await db.urls.create(
            data={
                "websiteName": "Stripe",
                "BaseUrl": "https://docs.stripe.com/api/",
                "desc": "Stripe doc.",
                "strictCheck":True,
                "inPipeline":True
            }
        )
        print("Created seed URL: https://docs.stripe.com/api/")
    else:
        print("Seed URL already exists.")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
