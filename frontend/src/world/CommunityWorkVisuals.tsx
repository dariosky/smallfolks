import type { World } from "../api/world";

export function CommunityWorkVisuals({ world }: { world: World }) {
  return (
    <g className="community-improvements">
      {(world.community_gardens ?? []).map((garden) => (
        <g
          key={garden.id}
          transform={`translate(${garden.position.x} ${garden.position.y})`}
          aria-label="Community flowerbed"
        >
          <title>Community flowerbed</title>
          <ellipse rx="22" ry="10" fill="#b99170" stroke="#735e4c" />
          {[-12, 0, 12].map((x) => (
            <g key={x} transform={`translate(${x} 0)`}>
              <path d="M0 4V-8m0 10-5-4m5 2 5-4" stroke="#58734b" fill="none" />
              <circle cy="-8" r="4" fill={x === 0 ? "#e7b762" : "#e97973"} />
            </g>
          ))}
        </g>
      ))}
      {world.places
        .filter(
          (place) => place.kind === "park" && place.cleanliness !== undefined,
        )
        .map((park) => (
          <text
            key={park.id}
            x={park.position.x}
            y={park.position.y + 48}
            textAnchor="middle"
            fontSize="10"
            fill="#496447"
            aria-label={`${park.name} cleanliness ${park.cleanliness}%`}
          >
            Cleanliness {park.cleanliness}%
          </text>
        ))}
    </g>
  );
}
