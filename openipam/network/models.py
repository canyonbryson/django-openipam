from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.db.models.signals import m2m_changed, post_save, pre_delete, pre_save
from django.utils import timezone

from netfields import InetAddressField, MACAddressField, CidrAddressField, NetManager

from taggit.managers import TaggableManager

from openipam.network.managers import LeaseManager, PoolManager, AddressManager, NetworkManager, DefaultPoolManager
from openipam.network.signals import validate_address_type, release_leases, set_default_pool
from openipam.user.signals import remove_obj_perms_connected_with_user


class Lease(models.Model):
    address = models.ForeignKey('Address', primary_key=True, db_column='address', related_name='leases')
    host = models.ForeignKey('hosts.Host', db_column='mac', db_constraint=False, related_name='leases', unique=True, null=True)
    abandoned = models.BooleanField(default=False)
    server = models.CharField(max_length=255, blank=True, null=True)
    starts = models.DateTimeField()
    ends = models.DateTimeField()

    objects = LeaseManager()

    def __unicode__(self):
        return '%s' % self.pk

    @property
    def is_expired(self):
        return True if self.ends <= timezone.now() else False

    @property
    def gul_last_seen(self):
        from openipam.hosts.models import GulRecentArpByaddress

        try:
            return GulRecentArpByaddress.objects.get(address=self.address.address).stopstamp
        except GulRecentArpByaddress.DoesNotExist:
            return None

    @property
    def gul_last_seen_mac(self):
        from openipam.hosts.models import GulRecentArpByaddress

        if self.mac:
            try:
                return GulRecentArpByaddress.objects.get(address=self.address.address).mac
            except GulRecentArpByaddress.DoesNotExist:
                return None
        else:
            return None

    class Meta:
        db_table = 'leases'


class Pool(models.Model):
    name = models.SlugField()
    description = models.TextField(blank=True)
    allow_unknown = models.BooleanField(default=False)
    lease_time = models.IntegerField()
    assignable = models.BooleanField(default=False)
    dhcp_group = models.ForeignKey('DhcpGroup', null=True, db_column='dhcp_group', blank=True)

    objects = PoolManager()

    def __unicode__(self):
        return self.name

    class Meta:
        db_table = 'pools'
        permissions = (
            ('add_records_to_pool', 'Can add records to'),
        )


class DefaultPool(models.Model):
    pool = models.ForeignKey('Pool', related_name='pool_defaults', blank=True, null=True)
    cidr = CidrAddressField(unique=True)

    objects = DefaultPoolManager()

    def __unicode__(self):
        return '%s - %s' % (self.pool, self.cidr)

    class Meta:
        db_table = 'default_pools'


class DhcpGroupManager(models.Manager):

    def get_query_set(self):
        qs = super(DhcpGroupManager, self).get_query_set()
        qs = qs.extra(select={'lname': 'lower(name)'}).order_by('lname')

        return qs


class DhcpGroup(models.Model):
    name = models.SlugField()
    description = models.TextField(blank=True, null=True)
    dhcp_options = models.ManyToManyField('DhcpOption', through='DhcpOptionToDhcpGroup')
    changed = models.DateTimeField(auto_now=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='changed_by')

    objects = DhcpGroupManager()

    def __unicode__(self):
        return '%s -- %s' % (self.name, self.description)

    class Meta:
        db_table = 'dhcp_groups'
        verbose_name = 'DHCP group'


class DhcpOption(models.Model):
    size = models.CharField(max_length=10, blank=True, null=True)
    name = models.CharField(max_length=255, unique=True, blank=True, null=True)
    option = models.CharField(max_length=255, unique=True, blank=True, null=True)
    comment = models.TextField(blank=True, null=True)

    def __unicode__(self):
        return '%s_%s' % (self.id, self.name)

    class Meta:
        db_table = 'dhcp_options'
        verbose_name = 'DHCP option'


class DhcpOptionToDhcpGroup(models.Model):
    group = models.ForeignKey('DhcpGroup', null=True, db_column='gid', blank=True, related_name='option_values')
    option = models.ForeignKey('DhcpOption', null=True, db_column='oid', blank=True, related_name='group_values')
    value = models.BinaryField(blank=True, null=True)
    changed = models.DateTimeField(auto_now=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='changed_by')

    def __unicode__(self):
        return '%s:%s=%r' % (self.group.name, self.option.name, str(self.value))

    class Meta:
        db_table = 'dhcp_options_to_dhcp_groups'


class HostToPool(models.Model):
    host = models.ForeignKey('hosts.Host', db_column='mac', db_index=True, related_name='host_pools')
    pool = models.ForeignKey('Pool', db_index=True, related_name='host_pools')
    changed = models.DateTimeField(auto_now=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='changed_by')

    def __unicode__(self):
        return '%s %s' % (self.host.hostname, self.pool.name)

    class Meta:
        db_table = 'hosts_to_pools'


class SharedNetwork(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    changed = models.DateTimeField(auto_now=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='changed_by')

    def __unicode__(self):
        return self.name

    class Meta:
        db_table = 'shared_networks'


class Network(models.Model):
    network = CidrAddressField(primary_key=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    gateway = InetAddressField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    vlans = models.ManyToManyField('Vlan', through='NetworkToVlan', related_name='vlan_networks')
    dhcp_group = models.ForeignKey('DhcpGroup', db_column='dhcp_group', blank=True, null=True)
    shared_network = models.ForeignKey('SharedNetwork', db_column='shared_network', blank=True, null=True)
    changed = models.DateTimeField(auto_now=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='changed_by')

    objects = NetworkManager()
    tags = TaggableManager()

    # Forcing pk as string
    @property
    def pk(self):
        return str(self.network)

    def __unicode__(self):
        return '%s -- %s' % (self.network, self.name)

    class Meta:
        db_table = 'networks'
        permissions = (
            ('is_owner_network', 'Is owner'),
            ('add_records_to_network', 'Can add records to'),
        )
        ordering = ('network',)


class NetworkRange(models.Model):
    range = CidrAddressField(unique=True)

    objects = NetManager()

    def __unicode__(self):
        return '%s' % self.range

    class Meta:
        db_table = 'network_ranges'


class Vlan(models.Model):
    id = models.SmallIntegerField(primary_key=True)
    name = models.CharField(max_length=12)
    description = models.TextField(blank=True)
    changed = models.DateTimeField(null=True, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='changed_by')

    def __unicode__(self):
        return '%s %s' % (self.id, self.name)

    class Meta:
        db_table = 'vlans'


class NetworkToVlan(models.Model):
    network = models.ForeignKey('Network', primary_key=True, db_column='network')
    vlan = models.ForeignKey('Vlan', db_column='vlan')
    changed = models.DateTimeField(auto_now=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='changed_by')

    objects = NetManager()

    def __unicode__(self):
        return '%s %s' % (self.network, self.vlan)

    class Meta:
        db_table = 'networks_to_vlans'


class Address(models.Model):
    address = InetAddressField(primary_key=True)
    # Force manual removal of addresses so they are unassigned and properly re-classified
    host = models.ForeignKey('hosts.Host', db_column='mac', blank=True, null=True, related_name='addresses', on_delete=models.SET_NULL)
    pool = models.ForeignKey('Pool', db_column='pool', blank=True, null=True, on_delete=models.SET_NULL)
    reserved = models.BooleanField(default=False)
    # Do we want to allow deletion of a network with addresses referencing it?
    network = models.ForeignKey('Network', db_column='network', related_name='net_addresses')
    changed = models.DateTimeField(auto_now=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='changed_by')

    objects = AddressManager()

    def __unicode__(self):
        return unicode(self.address)

    @property
    def last_mac_seen(self):
        from openipam.hosts.models import GulRecentArpBymac
        gul_mac = GulRecentArpBymac.objects.filter(mac=self.mac).order_by('-stopstamp').first()
        return gul_mac[0].mac if gul_mac else None

    @property
    def last_seen(self):
        from openipam.hosts.models import GulRecentArpByaddress
        gul_ip = GulRecentArpByaddress.objects.filter(address=self.address).order_by('-stopstamp').first()
        return gul_ip.stopstamp if gul_ip else None

    def clean(self):
        if self.host and self.pool:
            raise ValidationError('Host and Pool cannot both be defined.  Choose one or the other.')
        elif (self.host or self.pool) and self.reserved:
            raise ValidationError('If a Host or Pool are defined, reserved must be false.')

    class Meta:
        db_table = 'addresses'
        verbose_name_plural = 'addresses'


class AddressTypeManager(models.Manager):

    def get_by_name(self, name):
        return AddressType.objects.get(name__iexact=name)


class AddressType(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    ranges = models.ManyToManyField('NetworkRange', blank=True, null=True, related_name='address_ranges')
    pool = models.ForeignKey('Pool', blank=True, null=True)
    is_default = models.BooleanField(default=False)

    objects = AddressTypeManager()

    def __unicode__(self):
        return self.description

    def clean(self):
        default = AddressType.objects.filter(is_default=True)
        if self.pk:
            default = default.exclude(pk=self.pk)

        if default:
            raise ValidationError(_('There can only be one default Address Type'))

    class Meta:
        db_table = 'addresstypes'
        ordering = ('name',)


# Network Signals
pre_save.connect(set_default_pool, sender=Address)
m2m_changed.connect(validate_address_type, sender=AddressType.ranges.through)
post_save.connect(release_leases, sender=Address)
pre_delete.connect(remove_obj_perms_connected_with_user, sender=Network)
pre_delete.connect(remove_obj_perms_connected_with_user, sender=DhcpOption)
