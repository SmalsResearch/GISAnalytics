import collections.abc
from functools import partial
from urllib.parse import urlencode

from geopy.exc import ConfigurationError, GeocoderQueryError
from geopy.geocoders.base import _DEFAULT_USER_AGENT, DEFAULT_SENTINEL, Geocoder
from geopy.location import Location
from geopy.util import logger

# To start libpostal: docker run -p 7070:8080 -d nominatimwrapper_libpostal
import urllib3
import json


__all__ = ("BestAddress", )


class BestAddress(Geocoder):
    
    _DEFAULT_NOMINATIM_WRAPPER_DOMAIN  ="10.1.0.45:7777"

    geocode_path = '/api/belgianAddress/v2/addresses'
    def __init__(
            self,
            *,
            timeout=DEFAULT_SENTINEL,
            proxies=DEFAULT_SENTINEL,
            domain=_DEFAULT_NOMINATIM_WRAPPER_DOMAIN,
            scheme="http",
            user_agent=None,
            ssl_context=DEFAULT_SENTINEL,
            adapter_factory=None
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
            namedetails=False,
            skip_house_number=False
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


      
        params = { 
            'crs': 'gps',
            'embed': 'true', 
            'addressStatus': 'current',
            
            'postCode': query["postcode"],
            'postName': query["city"],
            'streetName': query["street"]
        }
        if not skip_house_number:
            params['houseNumber'] = query["housenumber"]
        
        url = self._construct_url(self.api, params)
        logger.debug("%s.geocode: %s", self.__class__.__name__, url)
        callback = partial(self._parse_json, exactly_one=exactly_one)
        res =  self._call_geocoder(url, callback, timeout=timeout)
        if res :
            res.raw["precision"] = "street" if skip_house_number else "building"
        elif not skip_house_number :
            #print("Trying without house number")
            res = self.geocode(query, skip_house_number=True)
        return res


    def _parse_code(self, place):
        # Parse each resource.
        #print("place: ", place)
        if "items" not in place or len(place["items"]) == 0:
            return None
        res= place["items"][0]
        
        res_street = place["embedded"][res["street"]["href"]]["streetName"]
        res_street = coalesce(res_street, ["fr", "nl", "de"])

        res_city = place["embedded"][res["municipality"]["href"]]["municipalityName"]
        res_city = coalesce(res_city, ["fr", "nl", "de"])

        res_zipcode = place["embedded"][res["postalInfo"]["href"]]["postCode"]
       
        res_housenumber = res["houseNumber"]
        
        placename = f"{res_street}, {res_housenumber}, {res_zipcode} {res_city}"
    
       
        match = place["items"][0]
        
        if "gps" in res:
            #place["precision"] = "building"
            latitude  = res["gps"]["y"] 
            longitude = res["gps"]["x"] 
        else:
            return None
            place["precision"] = "country"
            latitude = 50.8361263
            longitude = 4.3382716 
        
        if latitude is not None and longitude is not None:
            latitude = float(latitude)
            longitude = float(longitude)
        return Location(placename,  (latitude, longitude), place)
        #return Location(placename, (latitude, longitude), match)

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
        
        
        
        
        
        
        
##############
def call_libpostal(address):
    http = urllib3.PoolManager()

    r = http.request(
        'GET',
        "http://10.1.0.45:7070/parser",
        fields={"query": address})
    try:
        res = json.loads(r.data.decode('utf-8'))
    except ValueError:
        print("Cannot decode result:")
        print(json.loads(r.data.decode('utf-8')))
        return 
    return res

def coalesce(dct, keys):
    for k in keys:
        if k in dct:
            return dct[k]
    return None

class LPostBestAddress(BestAddress):
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
            namedetails=False,
            skip_house_number=False
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


        # call libpostal  
        lpost= call_libpostal(query)

        lpost = {k: v for [v, k] in lpost}

        if "road" not in lpost and "house" in lpost:
            print(lpost)
            lpost["road"] = lpost["house"]
            
        for f in ["city", "road", "house_number","postcode"]:
            if f not in lpost:
                lpost[f] = ""
        
#print(lpost)
        params = { 
            'crs': 'gps',
            'embed': 'true', 
            'addressStatus': 'current',
            
            'postCode': lpost["postcode"],
            'postName': lpost["city"],
            'streetName': lpost["road"]
        }
        if not skip_house_number:
            params['houseNumber'] = lpost["house_number"]
        
        url = self._construct_url(self.api, params)
        logger.debug("%s.geocode: %s", self.__class__.__name__, url)
        callback = partial(self._parse_json, exactly_one=exactly_one)
        res =  self._call_geocoder(url, callback, timeout=timeout)
        if res :
            res.raw["precision"] = "street" if skip_house_number else "building"
        elif not skip_house_number :
            #print("Trying without house number")
            res = self.geocode(query, skip_house_number=True)
        return res


