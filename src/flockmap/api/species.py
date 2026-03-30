from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Response
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q

from flockmap.models.species import Species
from flockmap.schemas.schemas import SpeciesCreate, SpeciesRead, SpeciesUpdate

router = APIRouter(prefix="/species", tags=["species"])


def _to_read(s: Species) -> SpeciesRead:
    return SpeciesRead(
        id=s.id,
        common_name=s.common_name,
        scientific_name=s.scientific_name,
        family=s.family,
        rarity_rank=s.rarity_rank,
        is_rare=s.is_rare,
        has_image=s.image_data is not None,
    )


# ---- List / search -------------------------------------------------------

@router.get("", response_model=list[SpeciesRead])
async def list_species(
    family: str | None = Query(None),
    is_rare: bool | None = Query(None),
    q: str | None = Query(None, description="Search common or scientific name"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    qs = Species.all()
    if family:
        qs = qs.filter(family=family)
    if is_rare is not None:
        qs = qs.filter(is_rare=is_rare)
    if q:
        qs = qs.filter(Q(common_name__icontains=q) | Q(scientific_name__icontains=q))
    items = await qs.offset(offset).limit(limit)
    return [_to_read(s) for s in items]


@router.get("/{species_id}", response_model=SpeciesRead)
async def get_species(species_id: int):
    s = await Species.get_or_none(id=species_id)
    if not s:
        raise HTTPException(404, "Species not found")
    return _to_read(s)


# ---- Create / Update / Delete --------------------------------------------

@router.post("", response_model=SpeciesRead, status_code=201)
async def create_species(body: SpeciesCreate):
    try:
        s = await Species.create(**body.model_dump())
    except IntegrityError:
        raise HTTPException(409, "Species with that scientific name already exists")
    return _to_read(s)


@router.patch("/{species_id}", response_model=SpeciesRead)
async def update_species(species_id: int, body: SpeciesUpdate):
    s = await Species.get_or_none(id=species_id)
    if not s:
        raise HTTPException(404, "Species not found")
    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        await s.update_from_dict(update_data).save()
    return _to_read(s)


@router.delete("/{species_id}", status_code=204)
async def delete_species(species_id: int):
    deleted = await Species.filter(id=species_id).delete()
    if not deleted:
        raise HTTPException(404, "Species not found")


# ---- Image upload / download ---------------------------------------------

@router.put("/{species_id}/image", status_code=204)
async def upload_image(species_id: int, file: UploadFile = File(...)):
    s = await Species.get_or_none(id=species_id)
    if not s:
        raise HTTPException(404, "Species not found")

    if file.content_type not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(400, "Only PNG, JPEG and WebP images are accepted")

    data = await file.read()
    max_bytes = 512 * 1024  # 512 KB
    if len(data) > max_bytes:
        raise HTTPException(400, f"Image too large ({len(data)} bytes). Max is {max_bytes}.")

    s.image_data = data
    s.image_mime = file.content_type
    await s.save()


@router.get("/{species_id}/image")
async def get_image(species_id: int):
    s = await Species.get_or_none(id=species_id)
    if not s or not s.image_data:
        raise HTTPException(404, "No image for this species")
    return Response(content=s.image_data, media_type=s.image_mime)
