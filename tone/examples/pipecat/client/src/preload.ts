/**
 * Every face, loaded and decoded before the screen first shows one, so a change of mood is only a
 * move to another cell of an image already in memory: nothing to fetch, nothing to decode, no flicker.
 * The decoded images are kept here for the life of the page.
 */
const kept: HTMLImageElement[] = []

export async function preload(urls: string[], onLoaded: (done: number) => void): Promise<void> {
  let done = 0
  await Promise.all(
    urls.map(async (url) => {
      const img = new Image()
      img.src = url
      try {
        await img.decode()
      } catch {
        // A face that won't decode is drawn as it comes; the screen still works.
      }
      kept.push(img)
      onLoaded(++done)
    })
  )
}
