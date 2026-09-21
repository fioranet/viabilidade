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
import unicodedata

def _norm_city(s: str) -> str:
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    stripped = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return stripped.strip().lower()

def _is_city_match(result_address: dict, expected_city: str) -> bool:
    """Verifica se a cidade retornada pelo Nominatim bate com a cidade esperada (ViaCEP/BrasilAPI)."""
    if not expected_city or not result_address:
        return True
    exp = _norm_city(expected_city)
    for key in ["city", "town", "municipality", "city_district", "suburb", "village", "county"]:
        val = result_address.get(key)
        if val:
            v_norm = _norm_city(val)
            if exp in v_norm or v_norm in exp:
                return True
    return False

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

    async def _query_nominatim(self, address_query: str, expected_city: Optional[str] = None) -> Optional[GeocodedLocation]:
        """Consulta Nominatim (OpenStreetMap) com rate limit estrito de 1 req/s e filtro de cidade."""
        await self._wait_for_rate_limit()

        params = {
            "q": address_query,
            "format": "json",
            "limit": "5",
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
                    if data and isinstance(data, list):
                        for item in data:
                            addr = item.get("address", {})
                            if expected_city and not _is_city_match(addr, expected_city):
                                continue # Ignorar resultados de outras cidades
                            return GeocodedLocation(
                                query=address_query,
                                latitude=float(item["lat"]),
                                longitude=float(item["lon"]),
                                display_name=item.get("display_name", address_query),
                                source="nominatim",
                                confidence=float(item.get("importance", 0.5))
                            )
        except Exception as e:
            print(f"[Geocoding] Erro ao consultar Nominatim: {e}")
        
        return None

    async def _query_nominatim_structured(
        self,
        street: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        postalcode: Optional[str] = None,
        expected_city: Optional[str] = None
    ) -> Optional[GeocodedLocation]:
        """Consulta Nominatim via parâmetros estruturados para máxima acurácia."""
        await self._wait_for_rate_limit()

        params = {
            "format": "json",
            "limit": "5",
            "addressdetails": "1",
            "country": "Brasil"
        }
        if street:
            params["street"] = street
        if city:
            params["city"] = city
        if state:
            params["state"] = state
        if postalcode:
            params["postalcode"] = postalcode

        headers = {
            "User-Agent": NOMINATIM_USER_AGENT
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, list):
                        for item in data:
                            addr = item.get("address", {})
                            if expected_city and not _is_city_match(addr, expected_city):
                                continue
                            query_repr = f"{street or ''}, {city or ''}, {state or ''}".strip(", ")
                            return GeocodedLocation(
                                query=query_repr,
                                latitude=float(item["lat"]),
                                longitude=float(item["lon"]),
                                display_name=item.get("display_name", query_repr),
                                source="nominatim_structured",
                                confidence=float(item.get("importance", 0.5))
                            )
        except Exception as e:
            print(f"[Geocoding] Erro ao consultar Nominatim estruturado: {e}")

        return None

    async def geocode(self, query: str, number: Optional[str] = None) -> Optional[GeocodedLocation]:
        """
        Geocodifica qualquer entrada: Coordenadas, CEP ou Endereço completo.
        Se for CEP, prioriza busca estruturada e validação de município com fallback seguro.
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
            # Buscar dados de endereço no ViaCEP e BrasilAPI
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

            # Obter dados complementares e coordenadas de fallback do BrasilAPI
            bapi = await self._query_brasilapi_cep(cep)
            bapi_coords = None
            if bapi:
                if not street:
                    street = bapi.get("street", "")
                if not neighborhood:
                    neighborhood = bapi.get("neighborhood", "")
                if not city:
                    city = bapi.get("city", "")
                if not state:
                    state = bapi.get("state", "")
                bapi_coords = bapi.get("location", {}).get("coordinates", {})

            cep_formatted = f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep

            if street or city:
                # 3a. Busca Estruturada de Alta Precisão (impede confusão de cidade/estado)
                nom_result = None

                # Tentativa 1: Rua + Número + Cidade + Estado + CEP
                if clean_number and street:
                    nom_result = await self._query_nominatim_structured(
                        street=f"{street}, {clean_number}",
                        city=city,
                        state=state,
                        postalcode=cep_formatted,
                        expected_city=city
                    )

                # Tentativa 2: Rua + Número + Cidade + Estado (sem travar pelo CEP específico)
                if not nom_result and clean_number and street:
                    nom_result = await self._query_nominatim_structured(
                        street=f"{street}, {clean_number}",
                        city=city,
                        state=state,
                        expected_city=city
                    )

                # Tentativa 3: Rua + Cidade + Estado + CEP
                if not nom_result and street:
                    nom_result = await self._query_nominatim_structured(
                        street=street,
                        city=city,
                        state=state,
                        postalcode=cep_formatted,
                        expected_city=city
                    )

                # Tentativa 4: Rua + Cidade + Estado
                if not nom_result and street:
                    nom_result = await self._query_nominatim_structured(
                        street=street,
                        city=city,
                        state=state,
                        expected_city=city
                    )

                # Tentativa 5: Cidade + CEP
                if not nom_result and cep_formatted:
                    nom_result = await self._query_nominatim_structured(
                        city=city,
                        state=state,
                        postalcode=cep_formatted,
                        expected_city=city
                    )

                # 3b. Se estruturada encontrou, formatar nome e retornar
                if nom_result:
                    num_text = f", {clean_number}" if clean_number else ""
                    bairro_text = f", {neighborhood}" if neighborhood else ""
                    nom_result.display_name = f"{street}{num_text}{bairro_text}, {city} - {state}, CEP {cep_formatted}"
                    nom_result.source = "viacep_nominatim"
                    self._cache[cache_key] = nom_result
                    return nom_result

                # 3c. Fallback para coordenadas do BrasilAPI se Nominatim não localizou dentro do município
                if bapi_coords and bapi_coords.get("latitude") and bapi_coords.get("longitude"):
                    try:
                        lat_val = float(bapi_coords["latitude"])
                        lon_val = float(bapi_coords["longitude"])
                        num_text = f", {clean_number}" if clean_number else ""
                        bairro_text = f", {neighborhood}" if neighborhood else ""
                        fallback_loc = GeocodedLocation(
                            query=query,
                            latitude=lat_val,
                            longitude=lon_val,
                            display_name=f"{street}{num_text}{bairro_text}, {city} - {state}, CEP {cep_formatted}",
                            source="brasilapi_cep",
                            confidence=0.8
                        )
                        self._cache[cache_key] = fallback_loc
                        return fallback_loc
                    except (ValueError, TypeError):
                        pass

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
