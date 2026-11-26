import sys
from collections import deque
from pathlib import Path

from PIL import Image

HOLE_MAX_PIXELS = 2500


def label_regions(grid, width, height, wanted):
    labels = [[-1] * width for _ in range(height)]
    regions = []
    for y in range(height):
        for x in range(width):
            if grid[y][x] == wanted and labels[y][x] < 0:
                index = len(regions)
                queue = deque([(x, y)])
                labels[y][x] = index
                points = []
                while queue:
                    px, py = queue.popleft()
                    points.append((px, py))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = px + dx, py + dy
                        if 0 <= nx < width and 0 <= ny < height and grid[ny][nx] == wanted and labels[ny][nx] < 0:
                            labels[ny][nx] = index
                            queue.append((nx, ny))
                regions.append(points)
    return labels, regions


def copper_groups(png_path):
    image = Image.open(png_path).convert("L")
    width, height = image.size
    pixels = image.load()
    grid = [[pixels[x, y] > 128 for x in range(width)] for y in range(height)]
    _, whites = label_regions(grid, width, height, True)
    holes = []
    for points in whites:
        if len(points) < HOLE_MAX_PIXELS:
            cx = sum(p[0] for p in points) // len(points)
            cy = sum(p[1] for p in points) // len(points)
            holes.append((cx, cy))
            for x, y in points:
                grid[y][x] = False
    labels, _ = label_regions(grid, width, height, False)
    groups = {}
    for cx, cy in holes:
        groups.setdefault(labels[cy][cx], []).append((cx, cy))
    return [sorted(group) for group in groups.values()]


if __name__ == "__main__":
    for group in copper_groups(Path(sys.argv[1])):
        print(group)
