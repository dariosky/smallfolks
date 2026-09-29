from heapq import heappop, heappush
from itertools import pairwise
from math import hypot

Point = dict[str, int]

NODES: dict[str, Point] = {
    "walk:north-west": {"x": 365, "y": 170},
    "walk:centre": {"x": 365, "y": 350},
    "walk:south-west": {"x": 365, "y": 520},
    "walk:north-east": {"x": 850, "y": 235},
    "walk:east-centre": {"x": 850, "y": 350},
    "walk:south-east": {"x": 850, "y": 570},
}

EDGES = {
    "walk:north-west": ("walk:centre", "walk:north-east"),
    "walk:centre": ("walk:north-west", "walk:south-west", "walk:east-centre"),
    "walk:south-west": ("walk:centre", "walk:south-east"),
    "walk:north-east": ("walk:north-west", "walk:east-centre"),
    "walk:east-centre": ("walk:north-east", "walk:south-east", "walk:centre"),
    "walk:south-east": ("walk:east-centre", "walk:south-west"),
}


def _distance(left: Point, right: Point) -> float:
    return hypot(right["x"] - left["x"], right["y"] - left["y"])


def _nearest_node(position: Point) -> str:
    return min(NODES, key=lambda node_id: _distance(position, NODES[node_id]))


def _access_leg(position: Point, node: Point) -> list[Point]:
    corner = {"x": node["x"], "y": position["y"]}
    return [position, corner, node] if corner != position and corner != node else [position, node]


def _shortest_node_path(start_id: str, end_id: str) -> list[str]:
    queue: list[tuple[float, str]] = [(0, start_id)]
    previous: dict[str, str | None] = {start_id: None}
    distances = {start_id: 0.0}
    while queue:
        distance, node_id = heappop(queue)
        if node_id == end_id:
            break
        if distance > distances[node_id]:
            continue
        for neighbour in EDGES[node_id]:
            candidate = distance + _distance(NODES[node_id], NODES[neighbour])
            if candidate < distances.get(neighbour, float("inf")):
                distances[neighbour] = candidate
                previous[neighbour] = node_id
                heappush(queue, (candidate, neighbour))
    path = [end_id]
    while path[-1] != start_id:
        path.append(previous[path[-1]])
    return list(reversed(path))


def pedestrian_route(start: Point, destination: Point) -> list[Point]:
    start_node = _nearest_node(start)
    end_node = _nearest_node(destination)
    route = _access_leg(start, NODES[start_node])
    route.extend(NODES[node_id] for node_id in _shortest_node_path(start_node, end_node)[1:])
    destination_leg = _access_leg(destination, NODES[end_node])
    route.extend(reversed(destination_leg[:-1]))
    return _dedupe(route)


def route_length(route: list[Point]) -> float:
    return sum(_distance(start, end) for start, end in pairwise(route))


def position_on_route(route: list[Point], progress: float) -> Point:
    target_distance = route_length(route) * min(1, max(0, progress))
    travelled = 0.0
    for start, end in pairwise(route):
        segment_length = _distance(start, end)
        if travelled + segment_length >= target_distance:
            segment_progress = (target_distance - travelled) / segment_length
            return {
                "x": round(start["x"] + (end["x"] - start["x"]) * segment_progress),
                "y": round(start["y"] + (end["y"] - start["y"]) * segment_progress),
            }
        travelled += segment_length
    return dict(route[-1])


def _dedupe(points: list[Point]) -> list[Point]:
    result: list[Point] = []
    for point in points:
        if not result or point != result[-1]:
            result.append(dict(point))
    return result
