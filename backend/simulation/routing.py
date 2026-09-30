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
    length = route_length(route)
    if length == 0:
        return dict(route[-1])
    target_distance = length * min(1, max(0, progress))
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


def _road_segments(roads: list[dict]) -> list[tuple[Point, Point]]:
    return [
        ({"x": start[0], "y": start[1]}, {"x": end[0], "y": end[1]})
        for road in roads for start, end in pairwise(road["points"])
    ]


def _project_to_segment(point: Point, start: Point, end: Point) -> Point:
    dx, dy = end["x"] - start["x"], end["y"] - start["y"]
    fraction = max(0.0, min(1.0, (
        (point["x"] - start["x"]) * dx + (point["y"] - start["y"]) * dy
    ) / (dx * dx + dy * dy)))
    return {"x": round(start["x"] + fraction * dx), "y": round(start["y"] + fraction * dy)}


def nearest_road_point(roads: list[dict], point: Point) -> Point:
    return min(
        (_project_to_segment(point, start, end) for start, end in _road_segments(roads)),
        key=lambda candidate: _distance(point, candidate),
    )


def parking_point(roads: list[dict], place: Point) -> Point:
    """Use the shoulder facing the destination, a short walk from its entrance."""
    road = nearest_road_point(roads, place)
    dx, dy = place["x"] - road["x"], place["y"] - road["y"]
    length = hypot(dx, dy)
    if length == 0:
        return road
    return {"x": round(road["x"] + dx / length * 16), "y": round(road["y"] + dy / length * 16)}


def road_route(roads: list[dict], start: Point, destination: Point) -> list[Point]:
    """Find a connected road-centre route, including short parking connectors."""
    segments = _road_segments(roads)
    start_road = nearest_road_point(roads, start)
    end_road = nearest_road_point(roads, destination)
    nodes: dict[tuple[int, int], Point] = {}
    for left, right in segments:
        for point in (left, right, start_road, end_road):
            if _project_to_segment(point, left, right) == point:
                nodes[(point["x"], point["y"])] = point
        for other_left, other_right in segments:
            if left["y"] == right["y"] and other_left["x"] == other_right["x"]:
                crossing = {"x": other_left["x"], "y": left["y"]}
            elif left["x"] == right["x"] and other_left["y"] == other_right["y"]:
                crossing = {"x": left["x"], "y": other_left["y"]}
            else:
                continue
            if (_project_to_segment(crossing, left, right) == crossing
                and _project_to_segment(crossing, other_left, other_right) == crossing):
                nodes[(crossing["x"], crossing["y"])] = crossing
    edges: dict[tuple[int, int], list[tuple[float, tuple[int, int]]]] = {
        key: [] for key in nodes
    }
    for left, right in segments:
        on_segment = [key for key, point in nodes.items()
                      if _project_to_segment(point, left, right) == point]
        on_segment.sort(key=lambda key: (key[0], key[1]))
        for a, b in pairwise(on_segment):
            length = _distance(nodes[a], nodes[b])
            edges[a].append((length, b))
            edges[b].append((length, a))
    source = (start_road["x"], start_road["y"])
    target = (end_road["x"], end_road["y"])
    queue = [(0.0, source)]
    distances = {source: 0.0}
    previous: dict[tuple[int, int], tuple[int, int] | None] = {source: None}
    while queue:
        distance, key = heappop(queue)
        if key == target:
            break
        if distance > distances[key]:
            continue
        for length, neighbour in edges[key]:
            candidate = distance + length
            if candidate < distances.get(neighbour, float("inf")):
                distances[neighbour] = candidate
                previous[neighbour] = key
                heappush(queue, (candidate, neighbour))
    if target not in previous:
        raise ValueError("No connected road route to parking")
    keys = [target]
    while keys[-1] != source:
        keys.append(previous[keys[-1]])
    route = [start, *(nodes[key] for key in reversed(keys)), destination]
    return _dedupe(route)


def road_edge_ids(roads: list[dict], route: list[Point]) -> list[str]:
    """List only roads traversed by the route, excluding parking connectors."""
    result = []
    for start, end in pairwise(route):
        road_id = next((
            road["id"] for road in roads
            for left, right in _road_segments([road])
            if _project_to_segment(start, left, right) == start
            and _project_to_segment(end, left, right) == end
        ), None)
        if road_id and (not result or result[-1] != road_id):
            result.append(road_id)
    return result
