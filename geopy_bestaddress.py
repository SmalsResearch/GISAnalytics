""" Geopy module for BeSt Address API """
import collections.abc
from functools import partial  # , lru_cache
from urllib.parse import urlencode, quote_plus

from cachetools import cached
from cachetools.keys import hashkey

import re

import textdistance
from unidecode import unidecode

from geopy.exc import GeocoderQueryError, GeocoderAuthenticationFailure
from geopy.geocoders.base import DEFAULT_SENTINEL, Geocoder
from geopy.location import Location
from geopy.util import logger


from oauthlib.oauth2 import BackendApplicationClient
# from requests_oauthlib import OAuth2Session

__all__ = ("BestAddress", )


def coalesce(dct, keys):
    """ return the first value dct[k] for k in 'keys'"""
    for k in keys:
        if k in dct:
            return dct[k]
    return None


def set_precision(res, precision):
    if isinstance(res, list):
        for ar in res:
            if "addressPosition" in ar.raw and ar.raw["addressPosition"]["lambert72"]["x"] == 0:
                precision = precision+"_00"
                # print("precision: ", precision)

            ar.raw["precision"] = precision

    else:
        if "addressPosition" in res.raw and res.raw["addressPosition"]["lambert72"]["x"] == 0:
            precision = precision+"_00"
            # print("precision: ", precision)

        res.raw["precision"] = precision


remove_patterns = [(r"\(.+\)$",      ""),
                   (r" - .+$",      ""),
                   ("[, ]*(SN|ZN)$", ""),
                   ("' ", "'"),
                   (" [a-z\xBF-\xFF][. ]", " "),
                   ("[.]", " "),
                   (",[a-z\xBF-\xFF .'-]*$", " ")
                   ]


def clean_streetname(street_name):
    """ Clean a street name by removing patterns described in 'remove_patterns' """
    if street_name is None or len(str(street_name)) == 0:
        return ""

    for pat, rep in remove_patterns:
        street_name = re.sub(pat, rep, street_name, flags=re.I)

    return street_name


def clean_housenumber(housenumber):
    """ Clean a housenumber by keeping only the starting numeric part"""
    hn = re.match("^[0-9]+", housenumber)
    if hn:
        return hn[0]
    return housenumber


sim_functions = [textdistance.jaro_winkler,
                 textdistance.sorensen_dice,
                 lambda s1, s2: 1 - textdistance.damerau_levenshtein(s1, s2)/max(len(s1), len(s2))
                 ]


class BestAddress(Geocoder):
    """ Main geopy class"""

    _DEFAULT_BEST_DOMAIN = None

    authorization_path = "/api/oauth2/token"
    street_path        = "belgianAddress/v2/streets"         # noqa: E221
    address_path       = "belgianAddress/v2/addresses"       # noqa: E221
    postalinfo_path    = "belgianAddress/v2/postalInfos"     # noqa: E221
    municipality_path  = "belgianAddress/v2/municipalities"  # noqa: E221
    prefix             = "/api/best/v1/"                     # noqa: E221
    scope              = "BOSA"                              # noqa: E221

    call_count = 0

    def __init__(
            self,
            *,
            timeout=DEFAULT_SENTINEL,
            proxies=DEFAULT_SENTINEL,
            domain=_DEFAULT_BEST_DOMAIN,
            scheme="https",
            prefix=None,
            user_agent=None,
            ssl_context=DEFAULT_SENTINEL,
            adapter_factory=None,
            client_id=None,
            client_secret=None,
            token=None,
            belgov_trace_id=None,
            verbose=False,
            mode="simple",
            with_token=True,
            authorization_path=None,
            check_result=False
            # Make sure to synchronize the changes of this signature in the
            # inheriting classes (e.g. PickPoint).
    ):
        """

        :param int timeout:
            See :attr:`geopy.geocoders.options.default_timeout`.

        :param dict proxies:
            See :attr:`geopy.geocoders.options.default_proxies`.

        :param str domain: Domain where the target Nominatim service
            is hosted.

        :param str scheme:
            See :attr:`geopy.geocoders.options.default_scheme`.

        :param str user_agent:
            See :attr:`geopy.geocoders.options.default_user_agent`.

        :type ssl_context: :class:`ssl.SSLContext`
        :param ssl_context:
            See :attr:`geopy.geocoders.options.default_ssl_context`.

        :param callable adapter_factory:
            See :attr:`geopy.geocoders.options.default_adapter_factory`.

            .. versionadded:: 2.0
        """

        super().__init__(
            scheme=scheme,
            timeout=timeout,
            proxies=proxies,
            user_agent=user_agent,
            ssl_context=ssl_context,
            adapter_factory=adapter_factory
        )

        self.verbose = verbose
        self.client_id = client_id
        self.client_secret = client_secret

        self.domain = domain.strip('/')

        self.mode = mode
        self.check_result = check_result

        if prefix is not None:
            self.prefix = prefix

        if authorization_path:
            self.authorization_path = authorization_path

        self.with_token = with_token
        if token:

            self.token = {'access_token': token}
            if self.verbose:
                print("setting parameter token")

        else:
            self.token = None

        self.api_street       = "%s://%s%s%s" % (self.scheme, self.domain, self.prefix, self.street_path)        # noqa: E221
        self.api_address      = "%s://%s%s%s" % (self.scheme, self.domain, self.prefix, self.address_path)       # noqa: E221
        self.api_postalinfo   = "%s://%s%s%s" % (self.scheme, self.domain, self.prefix, self.postalinfo_path)    # noqa: E221
        self.api_municipality = "%s://%s%s%s" % (self.scheme, self.domain, self.prefix, self.municipality_path)  # noqa: E221

        self.authorization_url = "%s://%s%s%s" % (self.scheme, self.domain, "/", self.authorization_path)

        self.belgov_trace_id = belgov_trace_id

    def renew_token(self):
        """ Renew oauth token"""

        client = BackendApplicationClient(client_id=self.client_id)
        oauth = OAuth2Session(client=client, scope=self.scope)

        if self.verbose:
            print(self.authorization_url, self.client_secret, self.client_id)

        self.token = oauth.fetch_token(token_url=self.authorization_url, include_client_id=True, client_secret=self.client_secret)

        if self.verbose:
            print(f"token: {self.token}")

    def _construct_url(self, base_api, params):
        """
        Construct geocoding request url.
        The method can be overridden in Nominatim-based geocoders in order
        to extend URL parameters.

        :param str base_api: Geocoding function base address - self.api
            or self.reverse_api.

        :param dict params: Geocoding params.

        :return: string URL.
        """
        return "?".join((base_api, urlencode(params)))

    @cached(cache={}, key=lambda self, api_base, params, timeout, exactly_one, return_raw: hashkey(api_base, params, exactly_one, return_raw))
    def _call_api(self, api_base, params, timeout=DEFAULT_SENTINEL, exactly_one=True, return_raw=False):
        """ Call the api. If needed, renew token"""

        headers = {
            "BelGov-Trace-Id": self.belgov_trace_id,
        }

        params = dict(params)
        BestAddress.call_count += 1
        if self.token is None and self.with_token:
            self.renew_token()

            headers["Authorization"] = f"Bearer {self.token['access_token']}"

        url = self._construct_url(api_base, params)
        logger.debug("%s.geocode: %s", self.__class__.__name__, url)
        if self.verbose:
            print(f" url : {url}")
            print(f" headers: {headers}")
        callback = partial(self._parse_json, exactly_one=exactly_one, return_raw=return_raw)
        try:
            return self._call_geocoder(url, callback, headers=headers, timeout=timeout)
        except GeocoderAuthenticationFailure as gaf:
            print(gaf)
            print("Renew token...")
            self.renew_token()
            headers["Authorization"] = f"Bearer {self.token['access_token']}"

            return self._call_geocoder(url, callback, headers=headers, timeout=timeout)

        except GeocoderQueryError as exc:
            print("GeocoderQueryError")
            print(exc)
            raise exc

    def geocode(
            self,
            query,
            *,
            exactly_one=True,
            timeout=DEFAULT_SENTINEL,
            # limit=None,
            # addressdetails=False,
            # language=False,
            # geometry=None,
            # extratags=False,
            # country_codes=None,
            # viewbox=None,
            # bounded=False,
            # featuretype=None,
            # namedetails=False,
            # skip_house_number=False,
            return_raw=False

    ):
        """
        Return a location point by address.

        :param query: The address, query or a structured query
            you wish to geocode.

            For a structured query, provide a dictionary whose keys
            are one of: `street`, `city`, `county`, `state`, `country`, or
            `postalcode`. For more information, see Nominatim's
            documentation for `structured requests`:

                https://nominatim.org/release-docs/develop/api/Search

        :type query: dict or str

        :param bool exactly_one: Return one result or a list of results, if
            available.

        :param int timeout: Time, in seconds, to wait for the geocoding service
            to respond before raising a :class:`geopy.exc.GeocoderTimedOut`
            exception. Set this only if you wish to override, on this call
            only, the value set during the geocoder's initialization.

        :param int limit: Maximum amount of results to return from Nominatim.
            Unless exactly_one is set to False, limit will always be 1.

        :param bool addressdetails: If you want in *Location.raw* to include
            address details such as house_number, city_district, postcode, etc
            (in a structured form) set it to True

        :param str language: Preferred language in which to return results.
            Either uses standard
            `RFC2616 <http://www.ietf.org/rfc/rfc2616.txt>`_
            accept-language string or a simple comma-separated
            list of language codes.

        :param str geometry: If present, specifies whether the geocoding
            service should return the result's geometry in `wkt`, `svg`,
            `kml`, or `geojson` formats. This is available via the
            `raw` attribute on the returned :class:`geopy.location.Location`
            object.

        :param bool extratags: Include additional information in the result if available,
            e.g. wikipedia link, opening hours.

        :param country_codes: Limit search results
            to a specific country (or a list of countries).
            A country_code should be the ISO 3166-1alpha2 code,
            e.g. ``gb`` for the United Kingdom, ``de`` for Germany, etc.

        :type country_codes: str or list

        :type viewbox: list or tuple of 2 items of :class:`geopy.point.Point` or
            ``(latitude, longitude)`` or ``"%(latitude)s, %(longitude)s"``.

        :param viewbox: Prefer this area to find search results. By default this is
            treated as a hint, if you want to restrict results to this area,
            specify ``bounded=True`` as well.
            Example: ``[Point(22, 180), Point(-22, -180)]``.

        :param bool bounded: Restrict the results to only items contained
            within the bounding ``viewbox``.

        :param str featuretype: If present, restrict results to certain type of features.
            Allowed values: `country`, `state`, `city`, `settlement`.

        :param bool namedetails: If you want in *Location.raw* to include
            namedetails, set it to True. This will be a list of alternative names,
            including language variants, etc.

        :rtype: ``None``, :class:`geopy.location.Location` or a list of them, if
            ``exactly_one=False``.

        """

        if self.mode == "simple":
            sequence = [(self.api_address,       {"streetName":  query["street"],
                                                  "postCode": query["postcode"],
                                                  "houseNumber": query["housenumber"]},
                        "address")]

        elif self.mode == "simple_fuzzy":
            sequence = [(self.api_address,       {"streetName":  f"~{query['street']}",
                                                  "postCode": query["postcode"],
                                                  "houseNumber": query["housenumber"]},
                         "~address")]

        elif self.mode == "basic":
            sequence = [(self.api_address,       {"streetName":  query["street"],
                                                  "postCode": query["postcode"],
                                                  "houseNumber": query["housenumber"]},
                         "address"),
                        (self.api_address,       {"streetName":  query["street"], "postCode": query["postcode"]},
                         "street"),
                        (self.api_street,        {"name":  query["street"], "postCode": query["postcode"]},
                         "street2"),

                        (self.api_postalinfo,    {"postCode":  query["postcode"]},
                         "city_zip"),
                        (self.api_postalinfo,    {"name":      query["city"]},
                         "city_postalname"),
                        (self.api_municipality,  {"name":      query["city"]},
                         "city_municname")]

        elif self.mode == "basic_fuzzy":

            sequence = [(self.api_address,   {"streetName":  query["street"],
                                              "postCode": query["postcode"],
                                              "houseNumber": query["housenumber"]},
                         "address"),
                        (self.api_address,   {"streetName":  f"~{query['street']}",
                                              "postCode": query["postcode"],
                                              "houseNumber": query["housenumber"]},
                         "~address"),
                        (self.api_address,       {"streetName":  query["street"], "postCode": query["postcode"]},
                         "street"),
                        (self.api_address,       {"streetName":  f"~{query['street']}", "postCode": query["postcode"]},
                         "~street"),

                        (self.api_street,        {"name":  query["street"], "postCode": query["postcode"]},
                         "street2"),
                        (self.api_postalinfo,    {"postCode":  query["postcode"]},
                         "city_zip"),
                        (self.api_postalinfo,    {"name":      query["city"]},
                         "city_postalname"),
                        (self.api_municipality,  {"name":      query["city"]},
                         "city_municname")]

        elif self.mode == "advanced":

            sequence = [
                    (self.api_address,       {"streetName":  query["street"],
                                              "postCode": query["postcode"],
                                              "houseNumber": query["housenumber"]}, "address"),

                    (self.api_address,       {"streetName":  f"~{query['street']}",
                                              "postCode": query["postcode"],
                                              "houseNumber": query["housenumber"]}, "~address"),

                    (self.api_address,       {"streetName":  clean_streetname(query["street"]),
                                              "postCode": query["postcode"],
                                              "houseNumber": query["housenumber"]}, "address_cleanstr"),

                    (self.api_address,       {"streetName":  f"~{clean_streetname(query['street'])}",
                                              "postCode": query["postcode"],
                                              "houseNumber": query["housenumber"]}, "~address_cleanstr"),

                    (self.api_address,       {"streetName":  f"~{query['street']}",
                                              "postCode": query["postcode"],
                                              "houseNumber": clean_housenumber(query["housenumber"])}, "~address_cleanhn"),

                    (self.api_address,       {"streetName":  query["street"], "postCode": query["postcode"]}, "street"),
                    (self.api_address,       {"streetName":  f"~{query['street']}", "postCode": query["postcode"]}, "~street"),
                    (self.api_address,       {"streetName":  f"~{clean_streetname(query['street'])}", "postCode": query["postcode"]}, "~clean_street"),

                    (self.api_street,        {"name":  query["street"], "municipality_name": query["city"]}, "street2"),
                    (self.api_street,        {"name":  f"~{query['street']}", "municipality_name": query["city"]}, "~street2"),
                    (self.api_street,        {"name":  clean_streetname(query["street"]), "municipality_name": query["city"]}, "street2_cleanstr"),
                    (self.api_street,        {"name":  f"~{clean_streetname(query['street'])}", "municipality_name": query["city"]}, "~street2_cleanstr"),

                    (self.api_postalinfo,    {"postCode":  query["postcode"]}, "city_zip"),
                    (self.api_postalinfo,    {"name":      query["city"]},     "city_postalname"),
                    (self.api_municipality,  {"name":      query["city"]},     "city_municname")
                   ]

        else:
            print(f"Wrong mode {self.mode}!")
            return None

        for i, (api_base, params, precision) in enumerate(sequence):
            # print(precision)
            logger.debug("%s.geocode: %s - %s", self.__class__.__name__, api_base, params)

            addr_res = self._call_api(api_base, tuple(params.items()), timeout, exactly_one=exactly_one and not self.check_result, return_raw=return_raw)

            # print(f"addr_res: {addr_res}")
            logger.debug("%s.geocode: addr_res=%s", self.__class__.__name__, addr_res)
            # logger.debug("%s.geocode: addr_res=%s", self.__class__.__name__, "items" in  addr_res)
            # print(addr_res)
            if self.check_result:
                addr_res = self.filter_results(addr_res, query)

                if exactly_one and addr_res is not None:
                    addr_res = addr_res[0]

            if addr_res is not None and (not return_raw or "items" in addr_res and len(addr_res["items"]) > 0):
                if not return_raw:
                    # addr_res["precision"] = precision
                    set_precision(addr_res, precision)
                else:
                    addr_res["precision"] = precision
                    addr_res["nb_calls"] = i+1
                return addr_res

        return None

    def _parse_code(self, place):
        """ Parse each resource."""

        street_name = coalesce(place["hasStreetName"]["name"], ["fr", "nl", "de"]) if "hasStreetName" in place else None
        housenumber = place["houseNumber"] if "houseNumber" in place else None
        city_name = coalesce(place["hasMunicipality"]["name"], ["fr", "nl", "de"]) if "hasMunicipality" in place else None
        part_city_name = coalesce(place["hasPartOfMunicipality"]["name"], ["fr", "nl", "de"]) if "hasPartOfMunicipality" in place and "name" in place["hasPartOfMunicipality"] else None

        postcode = place["hasPostalInfo"]["postCode"] if "hasPostalInfo" in place else place["postCode"] if "postCode" in place else None
        city_name = coalesce(place["name"], ["fr", "nl", "de"]) if "name" in place else city_name

        coords = {'lat': 0, 'long': 0}

        if "addressPosition" in place and place["addressPosition"]["lambert72"]["x"] > 0:
            coords = place["addressPosition"]["wgs84"]

        return Location(f"{street_name}, {housenumber if housenumber else ''}, {postcode} {city_name} {'('+part_city_name+')' if part_city_name else ''}",
                        (coords['lat'], coords['long']),
                        place)

    def _parse_json(self, places, exactly_one, return_raw):
        """ Parse JSON result"""

        if return_raw:  # Do not convert BestAddress result in Location objects
            return places

        if not places:
            return None

        if "items" not in places or len(places["items"]) == 0:
            return None

        if self.verbose:
            print("_parse_json: places")
            print(places)

        if isinstance(places, collections.abc.Mapping) and 'error' in places:
            if places['error'] == 'Unable to geocode':
                # no results in reverse
                return None
            raise GeocoderQueryError(places['error'])

        if exactly_one:
            return self._parse_code(places["items"][0])
        return [self._parse_code(place) for place in places["items"]]

    def get_by_id(self, best_id, object_type="address", timeout=DEFAULT_SENTINEL):
        """ Call api by giving a BeSt Id"""
        if object_type == "address":
            url = self.api_address+"/"+quote_plus(best_id)
        elif object_type == "street":
            url = self.api_street+"/"+quote_plus(best_id)
        elif object_type == "postalinfo":
            url = self.api_postalinfo+"/"+quote_plus(best_id)
        elif object_type == "municipality":
            url = self.api_municipality+"/"+quote_plus(best_id)
        else:
            return {"error": f"Unknown object_type value '{object_type}'. Valid values are 'address', 'street', 'postalinfo' and 'municipality' "}

        if self.verbose:
            print(url)
        return self._call_api(url, tuple(), timeout, exactly_one=False, return_raw=True)

    def reverse(
            self,
            query,
            *,
            exactly_one=True,
            timeout=DEFAULT_SENTINEL,
            radius=15
    ):
        """ Reverse geocoding """
        try:
            lat, lon = self._coerce_point_to_string(query).split(',')
        except ValueError as exc:
            raise ValueError("Must be a coordinate pair or Point") from exc
        params = {
            'yLat': lat,
            'xLong': lon,
            'radius': radius,
        }

        return self._call_api(self.api_address, tuple(params.items()), timeout, exactly_one=exactly_one)

    def compare_street(self, street_out, street_in, threshold=0.9):
        """ Compare street_in and street_out using various similarity methods. Returns True iff they are considered as 'equal'"""
        street_name_replaces = {"av": "avenue",
                                r'bl?v?d': 'boulevard',
                                r'che?e?': 'chaussee'}
        if self.verbose:
            print(f"Compare '{street_out}' vs '{street_in}'")
        street_out = unidecode(street_out.lower())
        for str_in in re.split(r'[,\)\(]', unidecode(street_in.lower())):
            str_in = str_in.strip()
            if len(str_in) == 0:
                continue
            str_in_variants = [str_in]
            str_in_var = str_in
            for pat, repl in street_name_replaces.items():
                str_in_var = re.sub(pat, repl, str_in_var)
            if str_in_var != str_in:
                str_in_variants.append(str_in_var)
            for str_in in str_in_variants:
                for sim_fct in sim_functions:
                    sim = sim_fct(str_in, street_out)
                    if self.verbose:
                        print(f"{str_in} - {street_out}: {sim}")
                    if sim >= threshold:
                        return True
        return False

    def check_best_result(self, item, query):
        """ Returne True if:
            - no street name is found in result
            - at least one item has a street name close enough to intput street name
        """
        if "hasStreetName" not in item:
            return True

        for _, streetname in item["hasStreetName"]["name"].items():
            if self.compare_street(streetname, query["street"]):
                return True
        return False

    def filter_results(self, addr_res, query):
        """ filter out results in 'addr_res' too far away from query"""
        if addr_res is None:
            return None

        filtered_res = [res for res in addr_res if self.check_best_result(res.raw, query)]
        if len(filtered_res) == 0:
            return None
        return filtered_res
