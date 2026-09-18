import re
import time
import asyncio
from typing import Optional, Dict, Any
import httpx

from app.config import (
    NOMINATIM_URL,
    NOMINATIM_USER_AGENT,
    NOMINATIM_MIN_INTERVAL_SECONDS
)
from app.models.schemas import GeocodedLocation

class GeocodingService:
    """
    Serviço de geocodificação com respeito ao rate limit do Nominatim (1 req/s),
    fallback para ViaCEP/BrasilAPI e detecção de coordenadas diretas.
    """

    def __init__(self):
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()
        self._cache: Dict[str, GeocodedLocation] = {}

    def _parse_direct_coordinates(self, query: str) -> Optional[GeocodedLocation]:
        """Tenta identificar se a string de busca já são coordenadas (Lat, Lng)."""
        clean_query = query.strip()
        # Padrões comuns: "-23.5505, -46.6333" ou "-23.5505 -46.6333"
        coord_pattern = r"^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?)[,\s]+[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$"
        match = re.match(coord_pattern, clean_query)
        if match:
            parts = [p.strip() for p in re.split(r"[,\s]+", clean_query) if p.strip()]
            if len(parts) >= 2:
                try:
                    lat = float(parts[0])
                    lon = float(parts[1])
                    return GeocodedLocation(
                        query=query,
                        latitude=lat,
                        longitude=lon,
                        display_name=f"Coordenadas Diretas ({lat:.6f}, {lon:.6f})",
                        source="direct_coords",
                        confidence=1.0
                    )
                except ValueError:
                    pass
        return None

    def _extract_cep(self, query: str) -> Optional[str]:
        """Verifica se a query é ou contém um CEP brasileiro (8 dígitos)."""
        cep_match = re.search(r"\b(\d{5})[-.]?(\d{3})\b", query)
        if cep_match:
            return f"{cep_match.group(1)}{cep_match.group(2)}"
        return None

    async def _wait_for_rate_limit(self):
        """Garante que pelo menos NOMINATIM_MIN_INTERVAL_SECONDS se passaram desde a última requisição."""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < NOMINATIM_MIN_INTERVAL_SECONDS:
                sleep_time = NOMINATIM_MIN_INTERVAL_SECONDS - elapsed
                await asyncio.sleep(sleep_time)
            self._last_request_time = time.time()

    async def _query_viacep(self, cep: str) -> Optional[Dict[str, Any]]:
        """Consulta dados de endereço via ViaCEP."""
        url = f"https://viacep.com.br/ws/{cep}/json/"
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if not data.get("erro"):
                        return data
        except Exception:
            pass
        return None

    async def _query_brasilapi_cep(self, cep: str) -> Optional[Dict[str, Any]]:
        """Consulta dados de endereço via BrasilAPI (V2 traz coordenadas aproximadas de vários CEPs!)."""
        url = f"https://brasilapi.com.br/api/cep/v2/{cep}"
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return None

    async def _query_nominatim(self, address_query: str) -> Optional[GeocodedLocation]:
        """Consulta Nominatim (OpenStreetMap) com rate limit estrito de 1 req/s."""
        await self._wait_for_rate_limit()

        params = {
            "q": address_query,
            "format": "json",
            "limit": "1",
            "addressdetails": "1"
        }
        headers = {
            "User-Agent": NOMINATIM_USER_AGENT
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and len(data) > 0:
                        first_result = data[0]
                        return GeocodedLocation(
                            query=address_query,
                            latitude=float(first_result["lat"]),
                            longitude=float(first_result["lon"]),
                            display_name=first_result.get("display_name", address_query),
                            source="nominatim",
                            confidence=float(first_result.get("importance", 0.5))
                        )
        except Exception as e:
            print(f"[Geocoding] Erro ao consultar Nominatim: {e}")
        
        return None

    async def geocode(self, query: str, number: Optional[str] = None) -> Optional[GeocodedLocation]:
        """
        Geocodifica qualquer entrada: Coordenadas, CEP ou Endereço completo.
        Se for CEP, busca o logradouro real via ViaCEP e geocodifica a rua com o número via Nominatim.
        """
        if not query:
            return None

        clean_number = str(number).strip() if number else ""
        cache_key = f"{query.strip().lower()}|{clean_number}"

        # 1. Checar se já temos em cache
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 2. Checar coordenadas diretas
        direct_coord = self._parse_direct_coordinates(query)
        if direct_coord:
            self._cache[cache_key] = direct_coord
            return direct_coord

        # 3. Checar se é busca por CEP
        cep = self._extract_cep(query)
        if cep:
            # Buscar logradouro no ViaCEP / BrasilAPI para geocodificar a rua real
            viacep_data = await self._query_viacep(cep)
            street = ""
            neighborhood = ""
            city = ""
            state = ""

            if viacep_data and not viacep_data.get("erro"):
                street = viacep_data.get("logradouro", "")
                neighborhood = viacep_data.get("bairro", "")
                city = viacep_data.get("localidade", "")
                state = viacep_data.get("uf", "")
            else:
                # Tentar BrasilAPI apenas para os dados de rua
                bapi = await self._query_brasilapi_cep(cep)
                if bapi:
                    street = bapi.get("street", "")
                    neighborhood = bapi.get("neighborhood", "")
                    city = bapi.get("city", "")
                    state = bapi.get("state", "")

            if street or city:
                nom_candidates = []
                if clean_number and street:
                    nom_candidates.append(f"{street}, {clean_number}, {city}, Brasil")
                    if neighborhood:
                        nom_candidates.append(f"{street}, {clean_number}, {neighborhood}, {city}, Brasil")
                
                if street:
                    nom_candidates.append(f"{street}, {city}, Brasil")
                    if neighborhood:
                        nom_candidates.append(f"{street}, {neighborhood}, {city}, Brasil")
                elif city:
                    nom_candidates.append(f"{city}, {state}, Brasil" if state else f"{city}, Brasil")

                for candidate in nom_candidates:
                    nom_result = await self._query_nominatim(candidate)
                    if nom_result:
                        num_text = f", {clean_number}" if clean_number else ""
                        bairro_text = f", {neighborhood}" if neighborhood else ""
                        nom_result.display_name = f"{street}{num_text}{bairro_text}, {city} - {state}, CEP {cep}"
                        nom_result.source = "viacep_nominatim"
                        self._cache[cache_key] = nom_result
                        return nom_result

        # 4. Geocodificação convencional de endereço textual
        final_query = query.strip()
        if clean_number and clean_number not in final_query:
            final_query = f"{final_query}, {clean_number}"

        nom_result = await self._query_nominatim(final_query)
        if nom_result:
            self._cache[cache_key] = nom_result
            return nom_result

        return None

# Instância singleton global do serviço de geocodificação
geocoding_service = GeocodingService()
