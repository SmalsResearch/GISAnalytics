import collections.abc
from functools import partial
from urllib.parse import urlencode


import  json
import requests

from geopy.exc import ConfigurationError, GeocoderQueryError
from geopy.geocoders.base import _DEFAULT_USER_AGENT, DEFAULT_SENTINEL, Geocoder
from geopy.location import Location
from geopy.util import logger

__all__ = ("NominatimWrapper", )

class NominatimWrapper(Geocoder):
    
    _DEFAULT_NOMINATIM_WRAPPER_DOMAIN  ="nominatimwrapper.smalsrech.be"
    structured_query_params = {
        'streetName', 'street',
        'houseNumber', 'housenumber',
        'postCode', 'postcode',
        'postName', 'city',
        'countryName', 'country'
    }

    geocode_path = '/REST/nominatimWrapper/v1.0/geocode'
    def __init__(
            self,
            *,
            timeout=DEFAULT_SENTINEL,
            proxies=DEFAULT_SENTINEL,
            domain=_DEFAULT_NOMINATIM_WRAPPER_DOMAIN,
            scheme="http",
            user_agent=None,
            ssl_context=DEFAULT_SENTINEL,
            adapter_factory=None,
            withExtraHouseNumber=True
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
            adapter_factory=adapter_factory,
        )

        self.domain = domain.strip('/')
        self.withExtraHouseNumber = withExtraHouseNumber
        

        self.api = "%s://%s%s" % (self.scheme, self.domain, self.geocode_path)

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

    def geocode(
            self,
            query,
            *,
            exactly_one=True,
            timeout=DEFAULT_SENTINEL,
            limit=None,
            addressdetails=False,
            language=False,
            geometry=None,
            extratags=False,
            country_codes=None,
            viewbox=None,
            bounded=False,
            featuretype=None,
            namedetails=False
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
        # print("query: ", query)
        if isinstance(query, collections.abc.Mapping):
            addr_data = {
                key: val
                for key, val
                in query.items()
                if key in self.structured_query_params
            }
            mappings = {'city':'postName',
                        'housenumber': 'houseNumber',
                        'postcode': 'postCode',
                        'country': 'countryName',
                       'street': 'streetName'}
            
            for alt_name in mappings:
                if alt_name in query and mappings[alt_name] not in addr_data:
                    addr_data[mappings[alt_name]] = query[alt_name]
            
            # print(addr_data)
            # for alt_names= [ ('city', 'postName', 'postc
            
            # print("query:", query)
            # print("addr_data: ", addr_data)
            # print("struct param: ", self.structured_query_params)
        else:
            addr_data = {'fullAddress': query}
    
        # print(addr_data)
        params = ({
            "checkResult" : False,
            "structOsm" : False,
            "withRejected": False,
            "extraHouseNumber": self.withExtraHouseNumber,
            "mode": "short"
        })

        url = self._construct_url(self.api, params)
        logger.debug("%s.geocode: %s", self.__class__.__name__, url)
        callback = partial(self._parse_json, exactly_one=exactly_one)
        return self._call_geocoder(url, callback, addr_data, timeout=timeout)

    def _call_geocoder(self, url, callback, addr_data, timeout):

        timeout = (timeout if timeout is not DEFAULT_SENTINEL
                   else self.timeout)
        
        data = {"address": addr_data}

        try: 
            
            result = requests.post(
                url,
                json=data, timeout=timeout)
            #print(result)
            
            if result.status_code == 204:
                #print("No result!")
                #print(addr_data)
                #print(result.text)
                return
            elif result.status_code == 400:
                print("Argument error")
                print(result.text)
            
            #print(type(result.text))
            return callback(json.loads(result.text))
        except Exception as e:
            print("Exception !")
            print(addr_data)
            print(e)
            raise e

    def _parse_code(self, place):
        # Parse each resource.
        # print(place)
        if "match" not in place: 
            return None
        match = place["match"][0]
        
        latitude = match["output"].get('lat', None)
        longitude = match["output"].get('lon', None)
        placename = match["output"].get('displayName', None)
        if latitude is not None and longitude is not None:
            latitude = float(latitude)
            longitude = float(longitude)
            
        # print("placename: ", placename)
        return Location(placename, (latitude, longitude), match)

    def _parse_json(self, places, exactly_one):
        
        if not places:
            return None

        if isinstance(places, collections.abc.Mapping) and 'error' in places:
            
            if places['error'] == 'Unable to geocode':
                # no results in reverse
                return None
            else:
                raise GeocoderQueryError(places['error'])

        if not isinstance(places, collections.abc.Sequence):
            places = [places]
        if exactly_one:
            return self._parse_code(places[0])
        else:
            return [self._parse_code(place) for place in places]